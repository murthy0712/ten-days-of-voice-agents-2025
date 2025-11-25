"""
Personal Finance Tutor Agent
Company: PennySense Financial

This file mirrors the Day 4 Teach-the-Tutor pattern but for Personal Finance.
Features:
- Small JSON knowledge base (personal_finance_content.json) auto-created on first run.
- Three modes: learn (Matthew), quiz (Alicia), teach_back (Ken).
- LiveKit agent integration placeholders and Murf TTS configuration.

Run: python personal_finance_agent.py

Replace Murf/LiveKit handoff stubs with your production handoff as needed.
"""

import logging
import json
import os
from dataclasses import dataclass
from typing import Literal, Optional, Annotated

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

# Plugins (same set as your biology agent)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("personal_finance_agent")
load_dotenv(".env.local")

# -----------------------------
# Company name
# -----------------------------
COMPANY_NAME = "PennySense Financial"

# -----------------------------
# Content file
# -----------------------------
DATA_DIR = "shared-data"
CONTENT_FILE = os.path.join(DATA_DIR, "personal_finance_content.json")

DEFAULT_CONTENT = [
    {
        "id": "budgeting",
        "title": "Budgeting",
        "summary": "Budgeting is the process of creating a plan to spend your money. It helps you ensure you have enough for essentials, build savings, and reach financial goals. A common method is the 50/30/20 rule: 50% needs, 30% wants, 20% savings/debt repayment.",
        "sample_question": "What is the 50/30/20 budgeting rule and why is it useful?"
    },
    {
        "id": "saving",
        "title": "Saving",
        "summary": "Saving means setting aside a portion of income for future use. Emergency funds typically cover 3-6 months of expenses. High-yield savings accounts provide better interest than standard checking accounts.",
        "sample_question": "How much should you aim to keep in an emergency fund and where should you keep it?"
    },
    {
        "id": "debt",
        "title": "Managing Debt",
        "summary": "Managing debt involves understanding interest rates, prioritizing high-interest debt repayments, and choosing strategies like the snowball (smallest balance first) or avalanche (highest interest first).",
        "sample_question": "Explain the difference between the debt snowball and debt avalanche methods."
    },
    {
        "id": "investing",
        "title": "Investing Basics",
        "summary": "Investing means putting money into assets (stocks, bonds, funds) with the expectation of growth. Diversification, time horizon, and risk tolerance are key concepts. Index funds are a low-cost way to get diversified exposure.",
        "sample_question": "Why is diversification important when investing?"
    }
]


def ensure_content_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONTENT_FILE):
        with open(CONTENT_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONTENT, f, indent=2)
        print(f"Created sample content at {CONTENT_FILE}")


def load_content():
    ensure_content_file()
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

COURSE_CONTENT = load_content()

# -----------------------------
# State
# -----------------------------
@dataclass
class TutorState:
    current_topic_id: Optional[str] = None
    current_topic_data: Optional[dict] = None
    mode: Literal["learn", "quiz", "teach_back"] = "learn"

    def set_topic(self, topic_id: str) -> bool:
        topic_id = topic_id.lower()
        topic = next((t for t in COURSE_CONTENT if t["id"] == topic_id), None)
        if topic:
            self.current_topic_id = topic_id
            self.current_topic_data = topic
            return True
        return False

@dataclass
class Userdata:
    tutor_state: TutorState
    agent_session: Optional[AgentSession] = None

# -----------------------------
# Tools
# -----------------------------
@function_tool
async def select_topic(
    ctx: RunContext[Userdata],
    topic_id: Annotated[str, Field(description="topic id to select")]
) -> str:
    state = ctx.userdata.tutor_state
    ok = state.set_topic(topic_id)
    if ok:
        return f"Topic set to {state.current_topic_data['title']}. Ask me to 'learn', 'quiz', or 'teach_back'."
    avail = ", ".join([t["id"] for t in COURSE_CONTENT])
    return f"Topic not found. Available topics: {avail}"

@function_tool
async def set_learning_mode(
    ctx: RunContext[Userdata],
    mode: Annotated[str, Field(description="learn | quiz | teach_back")]
) -> str:
    state = ctx.userdata.tutor_state
    mode = mode.lower()
    if mode not in ("learn", "quiz", "teach_back"):
        return "Mode must be one of: learn, quiz, teach_back"
    state.mode = mode

    s = ""
    session = ctx.userdata.agent_session
    if session:
        if mode == "learn":
            session.tts.update_options(voice="en-US-matthew", style="Promo")
            s = f"Mode LEARN. Ready to explain: {state.current_topic_data.get('title') if state.current_topic_data else 'no topic selected'}"
        elif mode == "quiz":
            session.tts.update_options(voice="en-US-alicia", style="Conversational")
            s = "Mode QUIZ. I will ask a question to test knowledge."
        else:
            session.tts.update_options(voice="en-US-ken", style="Promo")
            s = "Mode TEACH_BACK. Ask the user to explain the topic back to you."
    else:
        s = "Mode set locally. No active session for voice change."

    return f"Switched to {mode} mode. {s}"

@function_tool
async def evaluate_teaching(
    ctx: RunContext[Userdata],
    user_explanation: Annotated[str, Field(description="user's teach-back explanation")]
) -> str:
    # Very simple scoring: overlap with summary keywords
    topic = ctx.userdata.tutor_state.current_topic_data or {}
    summary = topic.get("summary", "")
    expected_words = set(w.strip('.,?!').lower() for w in summary.split())
    answer_words = set(w.strip('.,?!').lower() for w in user_explanation.split())
    if not expected_words:
        return "No topic selected to evaluate."
    overlap = expected_words & answer_words
    score = int( (len(overlap) / max(1, len(expected_words))) * 10 )
    if score >= 8:
        feedback = "Excellent — you covered most key points."
    elif score >= 5:
        feedback = "Good — you covered several important ideas."
    elif score >= 3:
        feedback = "A start — include more details and an example."
    else:
        feedback = "Needs work — try structuring your explanation and adding examples."
    return f"Score: {score}/10. {feedback}"

# -----------------------------
# Agent
# -----------------------------
class FinanceTutorAgent(Agent):
    def __init__(self):
        topic_list = ", ".join([f"{t['id']} ({t['title']})" for t in COURSE_CONTENT])
        super().__init__(
            instructions=f"""
            You are a Personal Finance Tutor for {COMPANY_NAME}.

            AVAILABLE TOPICS: {topic_list}

            MODES:
              - LEARN (voice: Matthew): explain the concept simply and give one practical example.
              - QUIZ (voice: Alicia): ask the sample_question from content and wait for a short answer.
              - TEACH_BACK (voice: Ken): ask the user to explain the concept back and provide corrective feedback.

            BEHAVIOR:
              - Start by asking which topic the user wants to study.
              - Use the tools select_topic, set_learning_mode, evaluate_teaching to manage state and scoring.
            """,
            tools=[select_topic, set_learning_mode, evaluate_teaching],
        )

# -----------------------------
# Entrypoint
# -----------------------------

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    print(f"Starting {COMPANY_NAME} - Personal Finance Tutor")
    userdata = Userdata(tutor_state=TutorState())

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(voice="en-US-matthew", style="Promo", text_pacing=True),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )

    userdata.agent_session = session

    await session.start(
        agent=FinanceTutorAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
