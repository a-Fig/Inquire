from dotenv import load_dotenv
import os
load_dotenv()

from livekit.plugins import groq
import prompts

os.environ["LIVEKIT_API_KEY"] = os.getenv("LIVEKIT_API_KEY")
os.environ["ELEVEN_API_KEY"] = os.getenv("ELEVEN_API_KEY")
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")


import main
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
)
from livekit.plugins import deepgram, elevenlabs, openai, silero

async def entrypoint(ctx: JobContext):
    await ctx.connect()

    agent = Agent(
        instructions=prompts.Mayday_Instructions,
    )
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=elevenlabs.TTS(),
    )

    await session.start(agent=agent, room=ctx.room)
    await session.generate_reply(instructions="Set up the experince, and begin the story.")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))