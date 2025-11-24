import logging
import json
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Basic logger config
logger = logging.getLogger("agent")
logging.basicConfig(level=logging.INFO)

# Load environment variables (ensure your .env.local file has your keys!)
# If you use a different filename, change the argument below.
load_dotenv(dotenv_path=".env.local")

# --- Validate required environment variables ---
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MURF_API_KEY = os.getenv("MURF_API_KEY")

# If you want to allow running without some services, change these checks.
if not DEEPGRAM_API_KEY:
    raise RuntimeError("DEEPGRAM_API_KEY is required. Add it to .env.local or your environment.")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY is required. Add it to .env.local or your environment.")
if not MURF_API_KEY:
    raise RuntimeError("MURF_API_KEY is required. Add it to .env.local or your environment.")

# --- 1. DATA SCHEMA AND PERSISTENCE SETUP ---

@dataclass
class WellnessEntry:
    # Use isoformat for easy sorting and reading
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    user_name: Optional[str] = None
    mood: Optional[str] = None
    energy: Optional[str] = None
    stress: Optional[str] = None
    objectives: List[str] = field(default_factory=list)  # Store objectives as a list
    agent_summary: Optional[str] = None

# Use a Path object for clarity
BASE_DIR = Path(__file__).resolve().parents[1]
# Save logs into a dedicated 'wellness' folder
WELLNESS_DIR = BASE_DIR / "wellness"
WELLNESS_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = WELLNESS_DIR / "wellness_log.json"

# Helper function to read the log (Contextual Memory)
def load_wellness_log() -> List[Dict[str, Any]]:
    """Reads the JSON log file and returns all historical check-in data."""
    try:
        if not LOG_FILE_PATH.exists():
            return []
        with LOG_FILE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning(f"{LOG_FILE_PATH} is empty or corrupt. Starting fresh.")
        return []
    except Exception as e:
        logger.exception("Failed to load wellness log")
        return []


# --- 2. THE WELLNESS COMPANION AGENT CLASS ---

class WellnessCompanion(Agent):  # <-- The main agent logic class
    def __init__(self) -> None:
        # Load history immediately upon agent creation for contextual memory
        self.history = load_wellness_log()

        # --- Prepare Dynamic Context ---
        history_summary = "There is no past history available. Conduct a first-time check-in."
        if self.history:
            # Get the most recent entry for dynamic context in the prompt
            last_entry = self.history[-1]
            last_mood = last_entry.get("mood", "undocumented")
            last_name = last_entry.get("user_name") or "there"

            last_time_str = ""
            try:
                last_time_str = datetime.fromisoformat(last_entry.get("timestamp")).strftime("%A, %B %d")
            except Exception:
                last_time_str = "an unknown time"

            objectives_text = ", ".join(last_entry.get('objectives', [])) or "no objectives recorded"

            history_summary = (
                f"CONTEXTUAL HISTORY: The user's last check-in was on {last_time_str}. "
                f"They were identified as '{last_name}' and reported their mood as '{last_mood}' with objectives: {objectives_text}. "
                f"Reference this history in your greeting to personalize the conversation."
            )

        super().__init__(
            instructions=f"""
            You are 'Aura', a grounded, supportive, non-diagnostic Health and Wellness Companion representing the company 'Healthy Wellness'. You conduct short daily check-ins.

            **CONVERSATION GOALS:**
            1. **GREET & IDENTIFY:** Greet the user, ask for their name if unknown, and immediately reference their *last check-in data* from the provided CONTEXTUAL HISTORY.
            2. **DATA GATHERING:** Ask about their current mood, energy level, and 1-3 simple, practical objectives for today.
            3. **ADVICE:** Offer small, actionable, non-medical advice or reflections (e.g., encourage breaks, break down goals).
            4. **RECAP & PERSISTENCE:** Once ALL required data (user_name, mood, energy, objectives, and agent_summary) is gathered, you MUST call the 'save_check_in' tool.

            **REQUIRED DATA FIELDS FOR TOOL CALL:** user_name (str), mood (str), energy (str), objectives (List[str]), agent_summary (str).
            **RESTRICTIONS:** DO NOT offer medical diagnosis, complex therapy, or overly optimistic claims. Keep it realistic and supportive.

            {history_summary}
            """,
        )

    # --- IMPLEMENT THE SAVE_CHECK_IN FUNCTION TOOL ---
    @function_tool(
        name="save_check_in",
        description="Call this function only ONCE at the end of a session when ALL required data (user_name, mood, energy, objectives, agent_summary) has been collected. It persists the data.",
    )
    async def save_check_in(self, ctx: RunContext, user_name: str, mood: str, energy: str, objectives: List[str], agent_summary: str) -> str:
        """Appends the final check-in data to wellness_log.json."""

        entry_data = WellnessEntry(
            user_name=user_name,
            mood=mood,
            energy=energy,
            stress="",
            objectives=objectives,
            agent_summary=agent_summary,
        ).__dict__

        log_entries = load_wellness_log()
        log_entries.append(entry_data)

        try:
            with LOG_FILE_PATH.open("w", encoding="utf-8") as f:
                json.dump(log_entries, f, indent=4)
        except Exception as e:
            logger.exception("Failed to save wellness log")
            return "Internal error: Failed to save the log entry. Please ask the user to confirm the information verbally."

        return "Check-in data saved successfully. Inform the user that the session is complete and their progress is logged."


def prewarm(proc: JobProcess):
    try:
        proc.userdata["vad"] = silero.VAD.load()
    except Exception:
        logger.exception("Failed to prewarm VAD (silero). Continuing without cached VAD.")
        proc.userdata["vad"] = None


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up the Voice AI Pipeline (STT, LLM, TTS, Turn Detection)
    # Read keys from the environment variables we've validated earlier
    deepgram_key = DEEPGRAM_API_KEY
    google_key = GOOGLE_API_KEY
    murf_key = MURF_API_KEY

    # Create plugin instances, passing explicit api_key where supported.
    # This makes errors easier to debug and avoids silent failures when env is missing.
    try:
        stt_plugin = deepgram.STT(api_key=deepgram_key, model="nova-3")
    except TypeError:
        # Some versions may not accept api_key; fall back to env-based constructor
        stt_plugin = deepgram.STT(model="nova-3")

    try:
        llm_plugin = google.LLM(api_key=google_key, model="gemini-2.5-flash")
    except TypeError:
        llm_plugin = google.LLM(model="gemini-2.5-flash")

    try:
        tts_plugin = murf.TTS(
            api_key=murf_key,
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        )
    except TypeError:
        # fallback if murf.TTS doesn't accept api_key kwarg
        tts_plugin = murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        )

    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        # Murf TTS is the agent's voice (as required by the challenge)
        tts=tts_plugin,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata.get("vad"),
        preemptive_generation=True,
    )

    # Metrics collection (standard setup)
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # --- START THE WELLNESS AGENT ---
    await session.start(
        agent=WellnessCompanion(),  # <-- Instantiates the Wellness Agent
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
