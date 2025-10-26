"""
LiveKit Voice Agent - Quick Start
==================================
The simplest possible LiveKit voice agent to get you started.
Requires only OpenAI and Deepgram API keys.
"""
from typing import Dict, List, Tuple
import json
from dataclasses import dataclass, asdict
from threading import RLock

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, RunContext
from livekit.agents.llm import function_tool
from livekit.plugins import deepgram, elevenlabs, openai, silero, groq
from datetime import datetime
import prompts
import os

# Load environment variables
load_dotenv(".env")
os.environ["LIVEKIT_API_KEY"] = os.getenv("LIVEKIT_API_KEY")
os.environ["ELEVEN_API_KEY"] = os.getenv("ELEVEN_API_KEY")
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")


class Item:
    item_id: str
    name: str
    qty: int = 1
    description: str = ""
    note: str = ""

    def to_json(self) -> Dict:
        return asdict(self)


class Assistant(Agent):
    """Basic voice assistant with Airbnb booking capabilities."""

    def __init__(self):
        super().__init__(
            instructions=prompts.Mayday_Instructions
        )

        self._inv: Dict[str, Item] = {}
        self._lock = RLock()

        # Mock Airbnb database
        self.airbnbs = {
            "san francisco": [
                {
                    "id": "sf001",
                    "name": "Cozy Downtown Loft",
                    "address": "123 Market Street, San Francisco, CA",
                    "price": 150,
                    "amenities": ["WiFi", "Kitchen", "Workspace"],
                },
                {
                    "id": "sf002",
                    "name": "Victorian House with Bay Views",
                    "address": "456 Castro Street, San Francisco, CA",
                    "price": 220,
                    "amenities": ["WiFi", "Parking", "Washer/Dryer", "Bay Views"],
                },
                {
                    "id": "sf003",
                    "name": "Modern Studio near Golden Gate",
                    "address": "789 Presidio Avenue, San Francisco, CA",
                    "price": 180,
                    "amenities": ["WiFi", "Kitchen", "Pet Friendly"],
                },
            ],
            "new york": [
                {
                    "id": "ny001",
                    "name": "Brooklyn Brownstone Apartment",
                    "address": "321 Bedford Avenue, Brooklyn, NY",
                    "price": 175,
                    "amenities": ["WiFi", "Kitchen", "Backyard Access"],
                },
                {
                    "id": "ny002",
                    "name": "Manhattan Skyline Penthouse",
                    "address": "555 Fifth Avenue, Manhattan, NY",
                    "price": 350,
                    "amenities": ["WiFi", "Gym", "Doorman", "City Views"],
                },
                {
                    "id": "ny003",
                    "name": "Artsy East Village Loft",
                    "address": "88 Avenue A, Manhattan, NY",
                    "price": 195,
                    "amenities": ["WiFi", "Washer/Dryer", "Exposed Brick"],
                },
            ],
            "los angeles": [
                {
                    "id": "la001",
                    "name": "Venice Beach Bungalow",
                    "address": "234 Ocean Front Walk, Venice, CA",
                    "price": 200,
                    "amenities": ["WiFi", "Beach Access", "Patio"],
                },
                {
                    "id": "la002",
                    "name": "Hollywood Hills Villa",
                    "address": "777 Mulholland Drive, Los Angeles, CA",
                    "price": 400,
                    "amenities": ["WiFi", "Pool", "City Views", "Hot Tub"],
                },
            ],
        }

        # Track bookings
        self.bookings = []


async def entrypoint(ctx: agents.JobContext):
    """Entry point for the agent."""

    # Configure the voice pipeline with the essentials
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=elevenlabs.TTS(),
        vad=silero.VAD.load(),
    )

    # Start the session
    await session.start(
        room=ctx.room,
        agent=Assistant()
    )

    # Generate initial greeting
    await session.generate_reply(
        instructions="Set up the experince, and begin the story."
    )

if __name__ == "__main__":
    # Run the agent
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))