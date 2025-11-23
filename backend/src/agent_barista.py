import logging
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
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

# --- Logging ---
logger = logging.getLogger("agent_barista")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Load .env.local
load_dotenv(".env.local")

# --- Required environment variables ---
missing_keys = []
if not os.getenv("DEEPGRAM_API_KEY"):
    missing_keys.append("DEEPGRAM_API_KEY")
if not os.getenv("MURF_API_KEY"):
    missing_keys.append("MURF_API_KEY")

if missing_keys:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(missing_keys)}. "
        "Add them to your .env.local file."
    )

# --- Orders directory ---
ORDERS_DIR = Path("orders")
ORDERS_DIR.mkdir(parents=True, exist_ok=True)


# --- COFFEE ORDER MODEL ---
@dataclass
class CoffeeOrder:
    drinkType: Optional[str] = None
    size: Optional[str] = None
    milk: Optional[str] = None
    extras: List[str] = field(default_factory=list)
    name: Optional[str] = None


# --- BARISTA AGENT ---
class BaristaAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are 'Java Joe', a cheerful, energetic barista working at **Moon Bucks Coffee**. "
                "Your job is to take the customer's order. "
                "You must ask friendly clarifying questions until ALL fields are known: "
                "DRINK TYPE, SIZE, MILK, EXTRAS, and the CUSTOMER'S NAME. "
                "Once all five fields are known, call the tool `save_order` with the complete JSON object. "
                "Keep responses friendly, simple, and without complex formatting. "
                "Do NOT call the tool until the full order is complete."
            ),
        )

    @function_tool(
        name="save_order",
        description="Save the completed order (drinkType, size, milk, extras, name) to a JSON file."
    )
    async def save_completed_order(self, ctx: RunContext, final_order_data: dict) -> str:

        # Validate complete order
        required = ["drinkType", "size", "milk", "extras", "name"]
        missing = [k for k in required if not final_order_data.get(k)]

        if missing:
            return (
                f"I can't save this order yet! Missing fields: {', '.join(missing)}. "
                "Please provide the complete order."
            )

        # Safe filename
        customer_name = final_order_data["name"].replace(" ", "_")
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        filename = f"final_order_{customer_name}_{timestamp}.json"
        filepath = ORDERS_DIR / filename

        # Write JSON
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(final_order_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Order saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save order file: {e}")
            return "There was an error saving the order. Please try repeating it."

        extras_s = ", ".join(final_order_data['extras']) if final_order_data['extras'] else "none"

        # Human-friendly confirmation
        return (
            f"Your Moon Bucks order is saved! "
            f"{final_order_data['size']} {final_order_data['drinkType']} with {final_order_data['milk']} milk, "
            f"extras: {extras_s}, for {final_order_data['name']}. "
            "Your delicious drink is on the way!"
        )


# --- PREWARM ---
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


# --- ENTRYPOINT ---
async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        # Ears
        stt=deepgram.STT(api_key=os.getenv("DEEPGRAM_API_KEY"), model="nova-3"),

        # Brain
        llm=google.LLM(model="gemini-2.5-flash"),

        # Voice
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),

        # Speaking/Listening logic
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def on_metrics(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        logger.info(f"Usage summary: {usage_collector.get_summary()}")

    ctx.add_shutdown_callback(log_usage)

    # Start voice session
    await session.start(
        agent=BaristaAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC()
        ),
    )

    await ctx.connect()


# --- MAIN WORKER ---
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
