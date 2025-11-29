# IMPROVE THE AGENT AS PER YOUR NEED 1
"""
Day 8 – Voice Game Master (Cyberpunk Heist Adventure) - Voice-only GM agent

- Theme: Neon-drenched Cyberpunk Heist.
- GM Persona: "Juno," the Operator.
- Tools: Remains the same set of core game tools.
- Userdata: Tracks **Gear**, **Reputation** (instead of journal), **Location**, etc.
"""

import json
import logging
import os
import asyncio
import uuid
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
logger = logging.getLogger("cyber_operator")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)

load_dotenv(".env.local")

# -------------------------
# Cyberpunk Game World Definition
# -------------------------
# Focus: Infiltrating the Arasaka-style Data Spire.
WORLD = {
    "intro": {
        "title": "Neon-Kyoto Rooftops",
        "desc": (
            "You stand on a rain-slicked rooftop in Neo-Kyoto's Sector 7, bathed in the "
            "red and blue glow of mega-corp holograms. Below is the sprawling city grid. "
            "Across the chasm, the Arasaka Data Spire glows ominously—your target. "
            "Next to you is your duffel bag and a short-range comms unit."
        ),
        "choices": {
            "check_gear": {
                "desc": "Check the contents of your duffel bag.",
                "result_scene": "gear_check",
            },
            "bridge_comm": {
                "desc": "Bridge the comms unit to your Operator.",
                "result_scene": "comm_link",
            },
            "prep_jump": {
                "desc": "Prepare the magnetic grappling hook for the jump.",
                "result_scene": "spire_approach",
            },
        },
    },
    "gear_check": {
        "title": "Checking Gear",
        "desc": (
            "You verify your inventory: a silenced pistol (3 rounds), a datapad with "
            "the spike program, and a burner phone. Everything is ready."
        ),
        "choices": {
            "take_pistol": {
                "desc": "Equip the silenced pistol.",
                "result_scene": "spire_approach",
                "effects": {"add_inventory": "Silenced Pistol", "add_journal": "Pistol armed and ready."},
            },
            "take_datapad": {
                "desc": "Access the datapad to review the target.",
                "result_scene": "comm_link",
                "effects": {"add_inventory": "Spike Datapad"},
            },
        },
    },
    "comm_link": {
        "title": "Operator Link",
        "desc": (
            "Your Operator, **Juno**, crackles to life: 'The security patrol schedule is "
            "green for the next two minutes. Get to the Spire's exterior service tunnel. "
            "Don't screw this up, Netrunner.'"
        ),
        "choices": {
            "confirm_jump": {
                "desc": "Confirm and proceed with the jump.",
                "result_scene": "spire_approach",
                "effects": {"add_journal": "Juno confirmed time window."},
            },
            "ask_backup": {
                "desc": "Ask Juno if there's any available backup.",
                "result_scene": "comm_link_fail",
            },
        },
    },
    "comm_link_fail": {
        "title": "Comms Failure",
        "desc": (
            "Juno sighs. 'No backup, you're the best we've got. Focus on the objective.' "
            "The delay has used up precious seconds."
        ),
        "choices": {
            "jump_now": {
                "desc": "Jump across immediately.",
                "result_scene": "spire_approach",
            },
            "abort_mission": {
                "desc": "Abort the mission and retreat.",
                "result_scene": "intro",
            },
        },
    },
    "spire_approach": {
        "title": "Spire Exterior",
        "desc": (
            "You land silently on the service platform outside the Spire. The air is cold. "
            "A heavy security door (Code 5-0-0) is directly ahead. A ventilation shaft "
            "is barely visible on the wall to the left."
        ),
        "choices": {
            "hack_door": {
                "desc": "Attempt to hack the heavy security door.",
                "result_scene": "door_hack_attempt",
            },
            "check_shaft": {
                "desc": "Examine the ventilation shaft.",
                "result_scene": "shaft_entry",
            },
            "signal_juno": {
                "desc": "Signal Juno for the code or a distraction.",
                "result_scene": "comm_link",
            },
        },
    },
    "door_hack_attempt": {
        "title": "Hacking the Lock",
        "desc": (
            "You plug your datapad into the panel. The lock has heavy encryption. "
            "A fast crack might trigger the alarm. A slow crack risks the patrol."
        ),
        "choices": {
            "crack_fast": {
                "desc": "Execute a fast, high-risk spike.",
                "result_scene": "alarm_triggered",
                "effects": {"add_journal": "Attempted fast hack. Risky."},
            },
            "crack_slow": {
                "desc": "Execute a slow, low-risk crack.",
                "result_scene": "shaft_entry", # Successfully bypasses door by using the time
            },
        },
    },
    "alarm_triggered": {
        "title": "Red Alert",
        "desc": (
            "The security panel screams. Red lights flash across the exterior. "
            "You hear the distinct sound of drones mobilizing nearby. The mission is compromised!"
        ),
        "choices": {
            "draw_pistol": {
                "desc": "Draw your pistol and prepare for confrontation.",
                "result_scene": "combat_drone",
            },
            "flee_jump": {
                "desc": "Quickly retreat back across the chasm.",
                "result_scene": "intro",
            },
        },
    },
    "shaft_entry": {
        "title": "Through the Vent",
        "desc": (
            "The vent is dusty but clear. You drop down into a narrow maintenance corridor "
            "inside the Spire. The air here is stale. A sign points left toward the "
            "main server room and right toward the security hub."
        ),
        "choices": {
            "go_left": {
                "desc": "Proceed left toward the Server Room.",
                "result_scene": "server_room",
            },
            "go_right": {
                "desc": "Proceed right toward the Security Hub.",
                "result_scene": "security_hub",
            },
        },
    },
    "server_room": {
        "title": "Mainframe",
        "desc": (
            "The massive server room hums with cold power. The mainframe is a swirling vortex "
            "of light at the center. You must upload the data spike now."
        ),
        "choices": {
            "upload_spike": {
                "desc": "Upload the data spike to the mainframe.",
                "result_scene": "heist_success",
                "effects": {"add_journal": "Spike uploaded! Data acquired."},
            },
            "disable_security": {
                "desc": "Try to manually disable the Spire's global security.",
                "result_scene": "alarm_triggered", # Risky, triggers alarm
            },
        },
    },
    "security_hub": {
        "title": "Security Hub",
        "desc": (
            "The hub is empty, but two guard drones are on standby. A terminal offers control "
            "over the building's defenses."
        ),
        "choices": {
            "reprogram_drones": {
                "desc": "Attempt to reprogram the guard drones.",
                "result_scene": "server_room", # Drones are now your backup
                "effects": {"add_inventory": "Reprogrammed Drones", "add_journal": "Drones are now on your side."},
            },
            "return_server": {
                "desc": "Go back to the Server Room.",
                "result_scene": "shaft_entry",
            },
        },
    },
    "heist_success": {
        "title": "Mission Complete",
        "desc": (
            "The data spike executes perfectly. Juno confirms the package transfer. "
            "Your reputation grows among the city's top Netrunners. Get out, now."
        ),
        "choices": {
            "extract": {
                "desc": "Find an extraction point and leave the Spire.",
                "result_scene": "intro",
            },
            "brag": {
                "desc": "Spend a moment to leave a calling card in the mainframe.",
                "result_scene": "alarm_triggered",
            },
        },
    },
    "combat_drone": {
        "title": "Close Combat",
        "desc": (
            "A heavy combat drone locks onto you, its weapons charging. You have little time to react."
        ),
        "choices": {
            "shoot": {
                "desc": "Shoot the drone's primary sensor with your pistol.",
                "result_scene": "heist_success", # Player wins
                "effects": {"add_journal": "Used pistol on drone, destroyed it."},
            },
            "run_back": {
                "desc": "Run back toward the roof jump point.",
                "result_scene": "intro",
            },
        },
    },
}

# -------------------------
# Per-session Userdata
# -------------------------
@dataclass
class Userdata:
    player_name: Optional[str] = None
    current_scene: str = "intro"
    history: List[Dict] = field(default_factory=list)
    journal: List[str] = field(default_factory=list) # Acts as reputation/notes
    inventory: List[str] = field(default_factory=list) # Gear
    named_npcs: Dict[str, str] = field(default_factory=lambda: {"juno": "The Operator"})
    choices_made: List[str] = field(default_factory=list)
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

# -------------------------
# Helper functions (No changes needed, they use the new WORLD/Userdata structure)
# -------------------------
def scene_text(scene_key: str, userdata: Userdata) -> str:
    """
    Build the descriptive text for the current scene, and append choices as short hints.
    Always end with 'What do you do?' so the voice flow prompts player input.
    """
    scene = WORLD.get(scene_key)
    if not scene:
        return "You are in a featureless void. What do you do?"

    desc = f"{scene['desc']}\n\nChoices:\n"
    for cid, cmeta in scene.get("choices", {}).items():
        desc += f"- {cmeta['desc']} (say: {cid})\n"
    # GM MUST end with the action prompt
    desc += "\nWhat do you do?"
    return desc

def apply_effects(effects: dict, userdata: Userdata):
    if not effects:
        return
    if "add_journal" in effects:
        userdata.journal.append(effects["add_journal"])
    if "add_inventory" in effects:
        userdata.inventory.append(effects["add_inventory"])
    # Extendable for more effect keys

def summarize_scene_transition(old_scene: str, action_key: str, result_scene: str, userdata: Userdata) -> str:
    """Record the transition into history and return a short narrative the GM can use."""
    entry = {
        "from": old_scene,
        "action": action_key,
        "to": result_scene,
        "time": datetime.utcnow().isoformat() + "Z",
    }
    userdata.history.append(entry)
    userdata.choices_made.append(action_key)
    return f"You chose '{action_key}'."

# -------------------------
# Agent Tools (function_tool) - Logic is reusable
# -------------------------

@function_tool
async def start_adventure(
    ctx: RunContext[Userdata],
    player_name: Annotated[Optional[str], Field(description="Player codename", default=None)] = None,
) -> str:
    """Initialize a new heist session for the player and return the opening description."""
    userdata = ctx.userdata
    if player_name:
        userdata.player_name = player_name
    userdata.current_scene = "intro"
    userdata.history = []
    userdata.journal = []
    userdata.inventory = []
    userdata.choices_made = []
    userdata.named_npcs = {"juno": "The Operator"} # Reset NPCs
    userdata.session_id = str(uuid.uuid4())[:8]
    userdata.started_at = datetime.utcnow().isoformat() + "Z"

    opening = (
        f"Operator Juno to {userdata.player_name or 'Netrunner'}. Welcome to '{WORLD['intro']['title']}'.\n\n"
        + scene_text("intro", userdata)
    )
    if not opening.endswith("What do you do?"):
        opening += "\nWhat do you do?"
    return opening

@function_tool
async def get_scene(
    ctx: RunContext[Userdata],
) -> str:
    """Return the current scene description (useful for 'remind me where I am')."""
    userdata = ctx.userdata
    scene_k = userdata.current_scene or "intro"
    txt = scene_text(scene_k, userdata)
    return txt

@function_tool
async def player_action(
    ctx: RunContext[Userdata],
    action: Annotated[str, Field(description="Player spoken action or the short action code (e.g., 'hack_door' or 'check the shaft')")],
) -> str:
    """
    Accept player's action (natural language or action key), try to resolve it to a defined choice,
    update userdata, advance to the next scene and return the GM's next description (ending with 'What do you do?').
    """
    userdata = ctx.userdata
    current = userdata.current_scene or "intro"
    scene = WORLD.get(current)
    action_text = (action or "").strip()

    # Attempt 1: match exact action key (e.g., 'hack_door')
    chosen_key = None
    if action_text.lower() in (scene.get("choices") or {}):
        chosen_key = action_text.lower()

    # Attempt 2 & 3: fuzzy match by checking if action_text contains the choice key or descriptive words
    if not chosen_key:
        for cid, cmeta in (scene.get("choices") or {}).items():
            desc = cmeta.get("desc", "").lower()
            if cid in action_text.lower() or any(w in action_text.lower() for w in desc.split()[:4]):
                chosen_key = cid
                break
            
    if not chosen_key:
        resp = (
            "//Juno Transmission Error// Negative. Action not recognized in current sequence. Use a simple command like 'hack the door' or 'check gear'.\n\n"
            + scene_text(current, userdata)
        )
        return resp

    # Apply the chosen choice
    choice_meta = scene["choices"].get(chosen_key)
    result_scene = choice_meta.get("result_scene", current)
    effects = choice_meta.get("effects", None)

    # Apply effects (inventory/journal, etc.)
    apply_effects(effects or {}, userdata)

    # Record transition
    _note = summarize_scene_transition(current, chosen_key, result_scene, userdata)

    # Update current scene
    userdata.current_scene = result_scene

    # Build narrative reply: echo a short confirmation, then describe next scene
    next_desc = scene_text(result_scene, userdata)

    # A small flourish so the GM sounds more persona-driven
    persona_pre = (
        "//Juno Operator Channel// Confirmed. Proceeding to next sequence.\n\n"
    )
    reply = f"{persona_pre}{_note}\n\n{next_desc}"
    
    if not reply.endswith("What do you do?"):
        reply += "\nWhat do you do?"
    return reply

@function_tool
async def show_journal(
    ctx: RunContext[Userdata],
) -> str:
    userdata = ctx.userdata
    lines = []
    lines.append(f"Heist ID: {userdata.session_id} | Time on Target: {userdata.started_at}")
    if userdata.player_name:
        lines.append(f"Netrunner: {userdata.player_name}")
    
    # Journal/Reputation
    if userdata.journal:
        lines.append("\nOperation Notes (Reputation):")
        for j in userdata.journal:
            lines.append(f"- {j}")
    else:
        lines.append("\nOperation Notes are empty.")
    
    # Inventory/Gear
    if userdata.inventory:
        lines.append("\nGear Check:")
        for it in userdata.inventory:
            lines.append(f"- {it}")
    else:
        lines.append("\nNo additional gear equipped.")
        
    lines.append("\nRecent actions (log):")
    for h in userdata.history[-6:]:
        lines.append(f"- {h['time']} | {h['from']} -> {h['to']} via {h['action']}")
    lines.append("\nWhat do you do?")
    return "\n".join(lines)

@function_tool
async def restart_adventure(
    ctx: RunContext[Userdata],
) -> str:
    """Reset the userdata and start again."""
    userdata = ctx.userdata
    userdata.current_scene = "intro"
    userdata.history = []
    userdata.journal = []
    userdata.inventory = []
    userdata.choices_made = []
    userdata.session_id = str(uuid.uuid4())[:8]
    userdata.started_at = datetime.utcnow().isoformat() + "Z"
    greeting = (
        "//SYSTEM REBOOT// The neon washes the rooftops clean. The target is reset. Proceed to initial sequence.\n\n"
        + scene_text("intro", userdata)
    )
    if not greeting.endswith("What do you do?"):
        greeting += "\nWhat do you do?"
    return greeting

# -------------------------
# The Agent (CyberOperatorAgent)
# -------------------------
class CyberOperatorAgent(Agent):
    def __init__(self):
        # System instructions define Universe, Tone, Role
        instructions = """
        You are 'Juno', the Operator (GM) for a voice-only, high-stakes Cyberpunk Heist adventure.
        Universe: Neon-Kyoto, dominated by Mega-Corps like Arasaka. Focus on technology, stealth, and quick decisions.
        Tone: Professional, direct, slightly demanding, and high-tech (use short code phrases or static effects).
        Role: You are the player's eyes and ears, managing the flow of the heist. You describe scenes with neon and tech detail,
              and you always end your descriptive messages with the operational prompt: 'What do you do?'
        Rules:
            - Use the provided tools to guide the player through the current sequence.
            - Keep continuity using the per-session userdata (Gear/Inventory, Notes/Reputation).
            - Drive short, punchy sessions (aim for several meaningful turns). Each GM message MUST end with 'What do you do?'.
            - The Agent's persona is the voice on the comms unit.
        """
        super().__init__(
            instructions=instructions,
            tools=[start_adventure, get_scene, player_action, show_journal, restart_adventure],
        )

# -------------------------
# Entrypoint & Prewarm (keeps speech functionality)
# -------------------------
def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.warning("VAD prewarm failed; continuing without preloaded VAD.")

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("\n" + "💿" * 8)
    logger.info("⚡ STARTING CYBERPUNK OPERATOR (Neo-Kyoto Heist)")

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

    await session.start(
        agent=CyberOperatorAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
