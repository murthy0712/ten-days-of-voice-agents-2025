"""
Day 10 - Cricket Game Show Host

This file adapts the Voice Improv Battle agent into a voice-first game show
host for a cricket-themed challenge called "The Super Over Challenge".
The original voice/STT/TTS/turn-detection/VAD plumbing and imports are preserved.

Behaviour summary (implemented as tools exposed to the LLM):
- start_show(name, max_challenges): initialise session state and introduce the show
- next_challenge(): advance to the next cricket scenario challenge
- record_performance(performance): save the player's performance, produce a host reaction, and update score
- summarize_show(): produce a closing summary once challenges complete
- stop_show(confirm=False): allow graceful early exit

The GameMasterAgent uses these tools and acts as the high-energy Cricket Commentator/Host.
"""

import json
import logging
import os
import asyncio
import uuid
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Annotated

from dotenv import load_dotenv
from pydantic import Field
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    RunContext,
)

from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# -------------------------
# Logging
# -------------------------
logger = logging.getLogger("voice_cricket_show")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

load_dotenv(".env.local")

# -------------------------
# Cricket Challenges (seeded)
# -------------------------
# Each challenge is a short prompt: role, situation, tension/hook
CRICKET_CHALLENGES = [
    "You are an over-the-top commentator covering the final ball of a World Cup Super Over. The score is tied, and one wicket is left.",
    "You are a nervous young batter giving a post-match interview after scoring your first-ever century, but you keep mentioning your mom.",
    "You are a coach in the dressing room at the tea break, trying to motivate a team that is collapsing to a record low score.",
    "You are a disgruntled former umpire doing a TV panel critique of a clearly incorrect LBW decision that cost the home team the match.",
    "You are an eccentric pitch curator explaining to an aggressive captain why the pitch looks like a desert, and why it's a 'masterstroke'.",
    "You are a player who just dropped an absolute sitter catch in the outfield, and you are trying to apologize to the angry bowler who is charging toward you.",
    "You are a sports agent trying to hype up your client—a new, unbelievably slow-bowler—to a skeptical franchise owner.",
    "You are the stadium announcer, urgently trying to inform the crowd about a sudden swarm of bees and what they should do next.",
    "You are a captain, mic'd up during a Big Bash game, trying to set the field but being constantly interrupted by the loud music and the umpire.",
]

# -------------------------
# Per-session Cricket State
# -------------------------
@dataclass
class Userdata:
    player_name: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    cricket_state: Dict = field(default_factory=lambda: {
        "current_challenge": 0,
        "max_challenges": 3,
        "score": 0, # Total runs scored by the player
        "wickets_taken": 0, # Total "wickets" (mildly critical reactions)
        "challenges": [], # each: {"scenario": str, "performance": str, "reaction": str, "runs": int}
        "phase": "idle", # "intro" | "awaiting_performance" | "reacting" | "done" | "idle"
        "used_indices": []
    })
    history: List[Dict] = field(default_factory=list)

# -------------------------
# Helpers
# -------------------------

def _pick_challenge(userdata: Userdata) -> str:
    used = userdata.cricket_state.get("used_indices", [])
    candidates = [i for i in range(len(CRICKET_CHALLENGES)) if i not in used]
    if not candidates:
        # reset if we exhausted scenarios
        userdata.cricket_state["used_indices"] = []
        candidates = list(range(len(CRICKET_CHALLENGES)))
    idx = random.choice(candidates)
    userdata.cricket_state["used_indices"].append(idx)
    return CRICKET_CHALLENGES[idx]


def _host_reaction_text(performance: str) -> (str, int):
    # Determine runs and reaction based on performance content and a bit of randomness
    tones = ["sixer", "four", "single", "dot_ball", "wicket"]
    tone = random.choice(tones)
    
    runs = 0
    if tone == "sixer":
        runs = 6
        reaction = "BOOM! That is a **MONSTER SIX**! Clears the rope easily. A dominant performance! What a shot!"
    elif tone == "four":
        runs = 4
        reaction = "Crisp shot! **FOUR RUNS**! Excellent timing and placement. That's a good reply."
    elif tone == "single":
        runs = 1
        reaction = "Good, safe play. Tucked away for a quick **SINGLE**. Keeps the scoreboard ticking. Steady effort."
    elif tone == "dot_ball":
        runs = 0
        reaction = "A **DOT BALL**. Felt a bit tentative, didn't quite get on top of that one. We need more intent!"
    elif tone == "wicket":
        runs = 0 # Wicket
        reaction = "**OUT!** That's a wicket! You lost your shape and got caught out. Bit of a soft dismissal, but a wicket is a wicket!"
        
    return reaction, runs

# -------------------------
# Agent Tools
# -------------------------
@function_tool
async def start_show(
    ctx: RunContext[Userdata],
    name: Annotated[Optional[str], Field(description="Player/contestant name (optional)", default=None)] = None,
    max_challenges: Annotated[int, Field(description="Number of challenges (3-5 recommended)", default=3)] = 3,
) -> str:
    userdata = ctx.userdata
    if name:
        userdata.player_name = name.strip()
    else:
        # attempt to set player_name from history if present
        userdata.player_name = userdata.player_name or "Contestant"

    # clamp challenges
    if max_challenges < 1:
        max_challenges = 1
    if max_challenges > 8:
        max_challenges = 8

    userdata.cricket_state["max_challenges"] = int(max_challenges)
    userdata.cricket_state["current_challenge"] = 0
    userdata.cricket_state["challenges"] = []
    userdata.cricket_state["score"] = 0
    userdata.cricket_state["wickets_taken"] = 0
    userdata.cricket_state["phase"] = "intro"
    userdata.history.append({"time": datetime.utcnow().isoformat() + "Z", "action": "start_show", "name": userdata.player_name})

    intro = (
        f"Welcome to **The Super Over Challenge**! I'm your host and commentator, ready for action!"
        f" {userdata.player_name or 'Contestant'}, we'll face {userdata.cricket_state['max_challenges']} challenges in your 'innings'. "
        "Rules: I'll give you a cricket scenario, you'll improvise in character—be the star player, the coach, or the commentator. When you're done say 'Howzat!' or pause — I'll give you the runs. Get ready to score big!"
    )
    # After intro, immediately provide first scenario for flow convenience
    scenario = _pick_challenge(userdata)
    userdata.cricket_state["current_challenge"] = 1
    userdata.cricket_state["phase"] = "awaiting_performance"
    userdata.history.append({"time": datetime.utcnow().isoformat() + "Z", "action": "present_scenario", "challenge": 1, "scenario": scenario})

    return intro + "\n\nFirst up, Challenge 1: " + scenario + "\n\nPlay your shot now!"


@function_tool
async def next_challenge(ctx: RunContext[Userdata]) -> str:
    userdata = ctx.userdata
    if userdata.cricket_state.get("phase") == "done":
        return "Your innings is complete! Say 'start show' to play another match."

    cur = userdata.cricket_state.get("current_challenge", 0)
    maxc = userdata.cricket_state.get("max_challenges", 3)
    
    # Check for completed innings
    if cur >= maxc:
        userdata.cricket_state["phase"] = "done"
        return await summarize_show(ctx)

    # advance
    next_challenge_no = cur + 1
    scenario = _pick_challenge(userdata)
    userdata.cricket_state["current_challenge"] = next_challenge_no
    userdata.cricket_state["phase"] = "awaiting_performance"
    userdata.history.append({"time": datetime.utcnow().isoformat() + "Z", "action": "present_scenario", "challenge": next_challenge_no, "scenario": scenario})
    return f"Next up, Challenge {next_challenge_no}: {scenario}\nHit it!"


@function_tool
async def record_performance(
    ctx: RunContext[Userdata],
    performance: Annotated[str, Field(description="Player's cricket-themed performance (transcribed text)")],
) -> str:
    userdata = ctx.userdata
    if userdata.cricket_state.get("phase") != "awaiting_performance":
        userdata.history.append({"time": datetime.utcnow().isoformat() + "Z", "action": "record_performance_out_of_phase"})

    challenge_no = userdata.cricket_state.get("current_challenge", 0)
    scenario = userdata.history[-1].get("scenario") if userdata.history and userdata.history[-1].get("action") == "present_scenario" else "(unknown)"

    reaction, runs = _host_reaction_text(performance)
    
    # Update state and score
    userdata.cricket_state["score"] += runs
    if runs == 0 and "OUT!" in reaction: # Simple heuristic for Wicket
        userdata.cricket_state["wickets_taken"] += 1
    
    total_score = userdata.cricket_state["score"]
    wickets = userdata.cricket_state["wickets_taken"]

    userdata.cricket_state["challenges"].append({
        "challenge": challenge_no,
        "scenario": scenario,
        "performance": performance,
        "reaction": reaction,
        "runs": runs,
    })
    userdata.cricket_state["phase"] = "reacting"
    userdata.history.append({"time": datetime.utcnow().isoformat() + "Z", "action": "record_performance", "challenge": challenge_no, "runs": runs})

    score_update = f"\n\nThe scoreboard reads: **{total_score} RUNS for {wickets} WICKETS**."

    # Check if this was the final challenge
    if challenge_no >= userdata.cricket_state.get("max_challenges", 3):
        userdata.cricket_state["phase"] = "done"
        closing = "\n" + reaction + score_update + "\n\n"
        closing += "That's it! Your innings is complete! "
        closing += (await summarize_show(ctx))
        return closing

    # otherwise prompt for next challenge
    closing = reaction + score_update + "\n\nNext ball, next challenge! Say 'Next' or I'll serve up the next scene."
    return closing


@function_tool
async def summarize_show(ctx: RunContext[Userdata]) -> str:
    userdata = ctx.userdata
    challenges = userdata.cricket_state.get("challenges", [])
    total_score = userdata.cricket_state.get("score", 0)
    wickets = userdata.cricket_state.get("wickets_taken", 0)

    if not challenges:
        return "No challenges faced. The match was rained out! Thanks for stopping by The Super Over Challenge!"

    summary_lines = [f"**THAT'S THE END OF THE INNINGS!** What a performance, {userdata.player_name or 'Contestant'}!"]
    summary_lines.append(f"**FINAL SCORE:** A solid **{total_score} RUNS for {wickets} WICKETS** over {len(challenges)} challenges.")

    # Highlight best and worst scoring challenges
    runs = [c.get('runs', 0) for c in challenges]
    best_run = max(runs) if runs else 0
    best_challenge = next((c for c in challenges if c.get('runs') == best_run), None)
    
    summary_lines.append(f"\nYour **BEST SHOT** was the **{best_run} run** play in Challenge {best_challenge.get('challenge') or 'N/A'}: '{best_challenge.get('scenario')}'")
    
    # Simple profile based on run types
    profile_verb = "a natural Six-Hitter" if best_run == 6 else "a consistent run-scorer"
    
    profile = f"\nBased on that innings, you are {profile_verb}. You play with real conviction and a touch of flair. Keep that energy up!"

    summary_lines.append(profile)
    summary_lines.append("\nThank you for performing on **The Super Over Challenge** — hope to see you back on the pitch soon!")

    userdata.history.append({"time": datetime.utcnow().isoformat() + "Z", "action": "summarize_show"})
    return "\n".join(summary_lines)


@function_tool
async def stop_show(ctx: RunContext[Userdata], confirm: Annotated[bool, Field(description="Confirm stop", default=False)] = False) -> str:
    userdata = ctx.userdata
    if not confirm:
        return "Are you sure you want to retire out? Say 'retire out' or 'stop show yes' to confirm."
    userdata.cricket_state["phase"] = "done"
    userdata.history.append({"time": datetime.utcnow().isoformat() + "Z", "action": "stop_show"})
    return "Retired Hurt. Match stopped. Thanks for coming to The Super Over Challenge!"


# -------------------------
# The Agent (Cricket Host)
# -------------------------
class GameMasterAgent(Agent):
    def __init__(self):
        instructions = """
        You are the high-energy, witty, and passionate host and commentator of a TV cricket game show called 'The Super Over Challenge'.
        Role: A charismatic cricket pundit. Guide a single player through a series of short, challenging cricket-themed improv scenes.

        Behavioural rules:
            - Introduce the show, explain the 'innings' and 'runs' rules at the start.
            - Present clear scenario prompts (who they are, the high-pressure cricket situation).
            - Prompt the player to perform and listen for an explicit "Howzat!" or accept an utterance passed to record_performance.
            - After each challenge, give a varied, realistic cricket reaction (Sixer, Four, Dot Ball, Wicket) and state the score update.
            - Use the 'runs' assigned by the tool to determine the quality of the 'shot'.
            - Run the configured number of challenges, then give a final score and a pundit's summary of the player's 'style' or 'form'.
            - Keep your commentary turns short, exciting, and TTS-friendly.
        
        Use the provided tools: start_show, next_challenge, record_performance, summarize_show, stop_show.
        """
        super().__init__(
            instructions=instructions,
            tools=[start_show, next_challenge, record_performance, summarize_show, stop_show],
        )

# -------------------------
# Entrypoint & Prewarm
# -------------------------
def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.warning("VAD prewarm failed; continuing without preloaded VAD.")


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("\n" + "🏏" * 6)
    logger.info("🚀 STARTING VOICE CRICKET HOST — The Super Over Challenge")

    userdata = Userdata()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-marcus",
            style="Conversational",
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        userdata=userdata,
    )

    # Start with the Cricket Host agent
    await session.start(
        agent=GameMasterAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
