from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    noise_cancellation,
)
from livekit.plugins.google import realtime
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import get_weather, search_web, send_email, query_knowledge_base
import json
load_dotenv()


class Assistant(Agent):
    def __init__(self, session_id: str = None) -> None:
        
        # Modify the base instruction to include the session_id if present
        inst = AGENT_INSTRUCTION
        if session_id:
            inst += f"\n\nIMPORTANT: The student has uploaded a textbook. The session ID is '{session_id}'. " \
                    f"If the student asks a question about their textbook, lesson, or story, " \
                    f"ALWAYS use the `query_knowledge_base` tool with this session_id to find the answer."
        
        super().__init__(
            instructions=inst,
            llm=realtime.RealtimeModel(
                voice="Aoede",
                temperature=0.8,
            ),
            tools=[
                get_weather,
                search_web,
                send_email,
                query_knowledge_base
            ],
        )


async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    
    # Wait for the student to join so we can grab their metadata
    participant = await ctx.wait_for_participant()
    
    session_id = None
    if participant.metadata:
        try:
            meta = json.loads(participant.metadata)
            session_id = meta.get("session_id")
        except json.JSONDecodeError:
            pass

    session = AgentSession()

    await session.start(
        room=ctx.room,
        agent=Assistant(session_id=session_id),
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await session.generate_reply(
        instructions=SESSION_INSTRUCTION,
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))