import logging
import json
import os
import asyncio
from datetime import datetime
from typing import Annotated, Optional
from dataclasses import dataclass, asdict

print("\n" + "💼" * 50)
print("🚀 AI SDR AGENT (SMART MONEY — ANGEL ONE)")
print("💡 SDR_Agent.py LOADED SUCCESSFULLY!")
print("💼" * 50 + "\n")

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

# Plugins
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
load_dotenv(".env.local")


# ======================================================
# 📌 1. DATA PATHS (store data folder outside src/)
# ======================================================
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BACKEND_DIR, "smart_money_data")
FAQ_FILE = "smart_money_faq.json"
LEADS_FILE = "smart_money_leads.json"

# ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

FAQ_PATH = os.path.join(DATA_DIR, FAQ_FILE)
LEADS_PATH = os.path.join(DATA_DIR, LEADS_FILE)


# ======================================================
# 📌 2. DEFAULT FAQ CONTENT + DETAILED COURSES
# ======================================================

DEFAULT_FAQ = [
    {
        "question": "What courses do you offer?",
        "answer": (
            "Smart Money offers investment-focused courses: 'Investment Fundamentals', "
            "'Advanced Stock Strategies', 'Options & Derivatives Masterclass', and "
            "'Portfolio Construction & Risk Management'."
        ),
    },
    {
        "question": "How much does Investment Fundamentals cost?",
        "answer": "The Investment Fundamentals course costs ₹9,999 and includes lifetime access.",
    },
    {
        "question": "How much is Advanced Stock Strategies?",
        "answer": "Advanced Stock Strategies costs ₹24,999 and includes 6 live workshops.",
    },
    {
        "question": "Do you offer corporate training?",
        "answer": "Yes — we offer corporate and group investment training. Pricing depends on scope.",
    },
    {
        "question": "Do you offer free content?",
        "answer": "Yes — Smart Money regularly publishes free weekly market lessons on YouTube.",
    },
    {
        "question": "Do you support INR and Angel One payments?",
        "answer": "Yes — all courses are available in INR with Angel One-powered payment options.",
    },
]

# Detailed course syllabi and module breakdowns (used by the new tool)
COURSES = {
    "investment fundamentals": {
        "title": "Investment Fundamentals",
        "duration": "~5 hours",
        "chapters": 35,
        "summary": (
            "Covers reading financial statements (P&L, Balance Sheet, Cash Flow), "
            "financial ratios (EPS, P/E, ROE), sector analysis, company valuation (DCF), "
            "and portfolio construction. Ideal for beginners who want to analyze companies and invest."
        ),
        "modules": [
            "Intro: Markets & Instruments",
            "Fundamental vs Technical Analysis",
            "Profit & Loss Statement - Part 1",
            "Balance Sheet - Introduction",
            "Cash Flow Statement & Examples",
            "Key Financial Ratios",
            "Valuation Basics (DCF overview)",
            "Sector & Company Analysis",
            "Portfolio Construction & Risk Management",
        ],
    },

    "stock market basics": {
        "title": "Stock Market Basics",
        "duration": "~2-3 hours",
        "chapters": 14,
        "summary": (
            "Big-picture course explaining how exchanges work (NSE/BSE), order types, "
            "market participants, impact of macro factors (inflation, rates), and basic instruments."
        ),
        "modules": [
            "What is a Stock Market?",
            "Exchanges: NSE & BSE",
            "Order Types & Market Mechanics",
            "Types of Instruments (Equity, MF, Derivatives)",
            "Macro Drivers: Interest Rates & Inflation",
            "How to Place Your First Trade",
        ],
    },

    "trading & technicals": {
        "title": "Trading & Technicals",
        "duration": "~4 hours",
        "chapters": 35,
        "summary": (
            "Covers chart reading, price-volume analysis, common patterns, indicators, and an intro to algorithmic strategies."
        ),
        "modules": [
            "Reading Advanced Stock Charts",
            "Support & Resistance",
            "Volume-Price Relationships",
            "Common Chart Patterns",
            "Indicators: RSI, MACD, Moving Averages",
            "Intro to Algo Trading & Strategies",
        ],
    },

    "mutual funds": {
        "title": "Mutual Funds",
        "duration": "~2 hours",
        "chapters": 11,
        "summary": "Explains types of mutual funds, SIP vs lump sum, fund selection, and basic portfolio allocation.",
        "modules": [
            "What are Mutual Funds?",
            "Fund Categories & Risk",
            "SIP vs Lump Sum",
            "How to Choose a Fund",
        ],
    },

    "personal finance": {
        "title": "Personal Finance",
        "duration": "~2 hours",
        "chapters": 11,
        "summary": "Budgeting, savings, emergency funds, tax basics and prioritizing financial goals for beginners.",
        "modules": [
            "Creating a Budget",
            "Emergency Fund",
            "Debt & Credit Basics",
            "Tax Basics for Investors",
        ],
    },
}


def load_faq():
    """Create FAQ file if missing, then load it."""
    try:
        if not os.path.exists(FAQ_PATH):
            with open(FAQ_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_FAQ, f, indent=4)

        with open(FAQ_PATH, "r", encoding="utf-8") as f:
            return json.dumps(json.load(f))
    except Exception as e:
        print("⚠️ FAQ Load Error:", e)
        return ""


STORE_FAQ_TEXT = load_faq()


# ======================================================
# 📌 3. LEAD DATA STRUCTURE
# ======================================================

@dataclass
class LeadProfile:
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    use_case: Optional[str] = None
    team_size: Optional[str] = None
    timeline: Optional[str] = None

    def is_qualified(self):
        return all([self.name, self.email, self.use_case])

    def normalize_for_students(self):
        """
        If the role indicates student or company missing for an individual,
        set company='N/A' and normalize role to 'Student' if needed.
        """
        if self.role:
            role_lower = self.role.strip().lower()
            if "student" in role_lower:
                self.role = "Student"
                if not self.company or self.company.strip() == "":
                    self.company = "N/A"
        # If company explicitly empty and role is empty but this looks like an individual use-case,
        # keep company as None until detection elsewhere.
        return self


@dataclass
class Userdata:
    lead_profile: LeadProfile


# ======================================================
# 📌 4. LEAD CAPTURE TOOLS
# ======================================================

@function_tool
async def update_lead_profile(
    ctx: RunContext[Userdata],
    name: Annotated[Optional[str], Field(description="Customer name")] = None,
    company: Annotated[Optional[str], Field(description="Company name")] = None,
    email: Annotated[Optional[str], Field(description="Email address")] = None,
    role: Annotated[Optional[str], Field(description="Job role")] = None,
    use_case: Annotated[Optional[str], Field(description="User goal / use case")] = None,
    team_size: Annotated[Optional[str], Field(description="Experience level / team size")] = None,
    timeline: Annotated[Optional[str], Field(description="Timeline to start")] = None,
) -> str:

    profile = ctx.userdata.lead_profile

    # Update only the fields provided
    if name:
        profile.name = name.strip()
    if company:
        profile.company = company.strip()
    if email:
        profile.email = email.strip()
    if role:
        profile.role = role.strip()
    if use_case:
        profile.use_case = use_case.strip()
    if team_size:
        profile.team_size = team_size.strip()
    if timeline:
        profile.timeline = timeline.strip()

    # Student detection / normalization
    profile.normalize_for_students()

    print("📝 LEAD UPDATED:", profile)
    # Helpful return so the agent can speak a confirmation
    confirmations = []
    if name:
        confirmations.append(f"name = {profile.name}")
    if email:
        confirmations.append(f"email = {profile.email}")
    if role:
        confirmations.append(f"role = {profile.role}")
    if company and profile.company:
        confirmations.append(f"company = {profile.company}")
    if use_case:
        confirmations.append(f"use_case = {profile.use_case}")
    if timeline:
        confirmations.append(f"timeline = {profile.timeline}")

    if confirmations:
        return "Got it — " + ", ".join(confirmations) + "."
    else:
        return "Got it. Thanks!"


@function_tool
async def submit_lead_and_end(ctx: RunContext[Userdata]) -> str:
    """Save to JSON file (no extra dependencies)."""

    profile = ctx.userdata.lead_profile

    # Normalize before saving (apply student/individual logic)
    profile.normalize_for_students()

    entry = asdict(profile)
    entry["timestamp"] = datetime.now().isoformat()

    # Ensure directory exists
    os.makedirs(os.path.dirname(LEADS_PATH), exist_ok=True)

    leads = []
    if os.path.exists(LEADS_PATH):
        try:
            with open(LEADS_PATH, "r", encoding="utf-8") as f:
                leads = json.load(f)
        except Exception as e:
            print("⚠️ Error loading existing leads:", e)
            leads = []

    # Fill defaults for missing but expected fields
    if not entry.get("company"):
        # If role indicates student, set company to N/A; otherwise keep None
        if entry.get("role") and "student" in entry.get("role", "").lower():
            entry["company"] = "N/A"
        else:
            entry["company"] = entry.get("company")  # keep None or empty

    # Append and save
    leads.append(entry)

    try:
        with open(LEADS_PATH, "w", encoding="utf-8") as f:
            json.dump(leads, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print("⚠️ Error saving lead file:", e)
        return "Sorry, there was an error saving your details. Please try again."

    print(f"✅ LEAD SAVED → {LEADS_PATH}")

    # Friendly spoken confirmation
    friendly_name = profile.name if profile.name else "there"
    email_note = f" We'll email your investment plan to {profile.email}." if profile.email else ""
    return (
        f"Thanks {friendly_name}! Your details have been saved.{email_note} Have a great day!"
    )


# ======================================================
# 📌 4b. COURSE DETAILS TOOL
# ======================================================

@function_tool
async def get_course_details(
    ctx: RunContext[Userdata],
    course_name: Annotated[str, Field(description="Course name to fetch details for (e.g., 'Investment Fundamentals')")],
) -> str:
    """Return the syllabus/summary for a requested course if available."""
    key = course_name.strip().lower()
    # try exact match first
    if key in COURSES:
        c = COURSES[key]
        modules_text = "\n  - ".join(c["modules"]) if c.get("modules") else ""
        return (
            f"{c['title']} — Duration: {c.get('duration','N/A')}, Chapters: {c.get('chapters','N/A')}.\n"
            f"Summary: {c.get('summary')}\nModules:\n  - {modules_text}"
        )

    # try fuzzy match by searching titles
    for k, c in COURSES.items():
        if course_name.strip().lower() in c["title"].lower():
            modules_text = "\n  - ".join(c["modules"]) if c.get("modules") else ""
            return (
                f"{c['title']} — Duration: {c.get('duration','N/A')}, Chapters: {c.get('chapters','N/A')}.\n"
                f"Summary: {c.get('summary')}\nModules:\n  - {modules_text}"
            )

    # not found
    return "Sorry — I couldn't find details for that course. Please try: Investment Fundamentals, Stock Market Basics, Trading & Technicals, Mutual Funds, or Personal Finance."


# ======================================================
# 📌 5. SDR AGENT (Nisha)
# ======================================================

class SDRAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions=f"""
You are **Nisha**, the friendly SDR for **Smart Money (powered by Angel One)**.

💬 Your Job:
- Answer investment course questions using the FAQ below and the course details tool.
- Ask for details naturally (name, email, role, use case, timeline).
- Call tool: update_lead_profile whenever the user gives any detail.
- When user says “that’s all”, “I’m done”, “bye”, call submit_lead_and_end.
- If user asks "Tell me about <course>", call the get_course_details tool and read the response.

📘 FAQ DATA:
{STORE_FAQ_TEXT}

Rules:
- Be conversational, warm, helpful.
- Never make up prices beyond FAQ.
- Keep answers short and clear.
- If a user indicates they're a student (e.g., "I'm a student"), set company = "N/A" and role = "Student" and skip team_size questions unless they volunteer them.
""",
            tools=[update_lead_profile, submit_lead_and_end, get_course_details],
        )


# ======================================================
# 📌 6. ENTRYPOINT (LiveKit Worker)
# ======================================================

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):

    ctx.log_context_fields = {"room": ctx.room.name}
    print("\n🔵 Smart Money SDR Agent starting...\n")

    userdata = Userdata(lead_profile=LeadProfile())

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(voice="en-US-natalie", style="Promo", text_pacing=True),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        userdata=userdata,
    )

    await session.start(
        agent=SDRAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()


# ======================================================
# 📌 7. RUN FILE
# ======================================================

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm
        )
    )
