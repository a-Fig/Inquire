from typing import List, Tuple, Any, Optional

import tooled_llm
import InventoryStoreSystem as inv

import asyncio, time, uuid
from livekit.agents.llm import (
    LLM, LLMStream, ChatContext, ChatChunk, ChoiceDelta,
    FunctionTool, RawFunctionTool
)


class APIConnectOptions:
    def __init__(self, max_retry=3, retry_interval=2.0, timeout=10.0): ...

default_start_up_instructions = """
    This is your oppurtinty to setup the game. Make any tools calls you need to now 
    to start the game. You should also think about and craft your initial message to the player and then send it to them.
""".strip()


class Gamemaster:
    def __init__(self, story, start_up_instructions=default_start_up_instructions, debug: bool = False):
        self.start_up_instructions = start_up_instructions
        tools = inv.build_tools()

        self.messages_for_user: str = ""
        self.debug = debug

        msgtool = tooled_llm.Toolwrapper(
            "send_message",
            self.send_message_loop,
            """
            Action name: "send_message"
            Arguments: list of messages
            Purpose: This tool is the only way you are able to communicate with the player. The tool sends 1 or more messages to the player. Break up long messages with '\\n'.
            Returns: conformation with Success or Fail
            """,
        )

        tools.append(msgtool)

        instructions = f"""
            You are a game master. Your job is to guide the player through an evolving story, all based on their
            own choices. On every turn you should describe the world and game to the player so they know what is 
            going on and then give them an oppurtinty to ask you question or decide on an action for their player.
            After that you should process their response, decide how the story unfolds based on their action and
            then give them another oppurtinty. You should continue this loop until the game ends. 

            Remember to be descriptive in your speach. Your goal is to guide the player through an engaging
            and evolving story.

            Do not be scared to ask the Player for clarity in their responses or to tell them no if they want to do 
            something that is not possible or against the rules. You are the game MASTER, they are just a player.
            If they make a confusing or unclear statement you can and should ask them to be more clear.

            You have been given a number of tools to help you keep track of the games states, use them. 

            You should never call any tools after you have responded to the player.

            Below you will be told about the world / story you will be the game master for.

            {story}
        """.strip()

        self.master = tooled_llm.ToolLLM(instructions, tools, debug=debug)

    # --- message capture used by ToolLLM's send_message tool ---
    def send_message_loop(self, messages: List[str]) -> Tuple[bool, str]:
        if len(messages) == 0:
            return True, "error: empty message list"
        for msg in messages:
            self.messages_for_user += f"{msg}\n"
        return False, "Message sent"

    def send_message_prompt(self, messages: List[str]) -> Tuple[bool, str]:
        if len(messages) == 0:
            return True, "error: empty message list"
        for msg in messages:
            self.messages_for_user += f"{msg}\n"
        return False, "Message sent"

    def get_messages_for_user(self) -> str:
        temp = self.messages_for_user.strip()
        self.messages_for_user = ""
        return temp

    # --- public API you already used locally ---
    def start_message(self) -> str:
        self.master.tools["send_message"].action = self.send_message_prompt
        self.master.prompt(self.start_up_instructions)
        return self.get_messages_for_user()

    def prompt(self, user_message: str) -> str:
        self.master.tools["send_message"].action = self.send_message_prompt
        self.master.prompt(user_message)
        return self.get_messages_for_user()


class GameMasterLLMStream(LLMStream):
    """LiveKit-compatible LLMStream that wraps a GameMaster."""

    def __init__(
        self,
        llm: "GameMasterLLMAdapter",
        *,
        chat_ctx: ChatContext,
        tools: list[FunctionTool | RawFunctionTool],
        conn_options: APIConnectOptions,
    ):
        super().__init__(llm, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)

    async def _run(self) -> None:
        # 1. If this is the first turn, emit intro narration
        if not self._llm._started:
            intro = await asyncio.to_thread(self._llm.gm.start_message)
            if intro:
                self._event_ch.send_nowait(
                    ChatChunk(
                        id=str(uuid.uuid4()),
                        delta=ChoiceDelta(role="assistant", content=intro),
                    )
                )
            self._llm._started = True

        # 2. Extract the latest user message from ChatContext
        user_text = None
        for item in getattr(self.chat_ctx, "items", []):
            if getattr(item, "type", None) == "message" and getattr(item, "role", None) == "user":
                txt = getattr(item, "text_content", None)
                if txt:
                    user_text = txt

        if not user_text:
            # Nothing to reply to
            self._event_ch.send_nowait(
                ChatChunk(id=str(uuid.uuid4()), delta=ChoiceDelta(role="assistant", content=""))
            )
            return

        # 3. Call GameMaster synchronously in a thread to avoid blocking
        reply = await asyncio.to_thread(self._llm.gm.prompt, user_text)

        # 4. Send the response as one ChatChunk
        self._event_ch.send_nowait(
            ChatChunk(
                id=str(uuid.uuid4()),
                delta=ChoiceDelta(role="assistant", content=reply),
            )
        )

class GameMasterLLMAdapter(LLM):
    """Wraps a GameMaster instance so it behaves like a LiveKit LLM."""

    def __init__(self, gm: Gamemaster, model: str = "gamemaster-v0", provider: str = "custom"):
        super().__init__()
        self.gm = gm
        self._model = model
        self._provider = provider
        self._label = f"{self._provider}.{self._model}"
        self._started = False

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return self._provider

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list[FunctionTool | RawFunctionTool] | None = None,
        conn_options: APIConnectOptions = APIConnectOptions(max_retry=3, retry_interval=2.0, timeout=10.0),
        parallel_tool_calls=None,
        tool_choice=None,
        extra_kwargs=None,
    ) -> LLMStream:
        """Create a LiveKit-compatible stream that runs one GM turn."""
        return GameMasterLLMStream(self, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options)

# Convenience factory for integration
def _gm_as_livekit_llm(self, model: str = "gamemaster-v0", provider: str = "custom") -> GameMasterLLMAdapter:
    return GameMasterLLMAdapter(self, model=model, provider=provider)

Gamemaster.as_livekit_llm = _gm_as_livekit_llm
