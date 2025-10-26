from typing import List
import time

print("general_chat_api.py")

from dotenv import load_dotenv
import os
load_dotenv()

from groq import Groq
import asyncio

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

default_model = "llama-3.3-70b-versatile"

class FlashChat:
    def __init__(self, directions: str = "You are a helpful assistant.", model: str = default_model):
        self.model = model
        self.client = client
        self.directions = directions
        self.setup: bool = False
        self.history: list[dict] = [
            {"role": "system", "content": directions}
        ]

    def prompt(self, message: str = "") -> str:
        user_messsage = {"role": "user", "content": message}
        self.history.append(user_messsage)
        chat_completion = self.client.chat.completions.create(
            messages=self.history,
            model=self.model,
        )
        content = chat_completion.choices[0].message.content
        self.history.append({"role": "assistant", "content": content})
        return content

    async def aprompt(self, message: str = "") -> str:
        """Async-friendly wrapper so we don't block the LiveKit loop."""
        return await asyncio.to_thread(self.prompt, message)

    def pop_message(self):
        return self.history.pop()

    def append_message(self, role: str, text: str):
        self.history.append({"role": role, "content": text})

    def rewrite_message(self, i: int, text: str):
        self.history[i]["content"] = text

    def rewrite_last_message(self, text: str):
        self.rewrite_message(-1, text)

    def safe_prompt(self, message: str, max_tries: int = 5, base_backoff: float = 10.0, debug: bool = False):
        return self.prompt(message)

    def chat_history(self, user_label: str = "user> ", model_label: str = "model> ", user_end_label: str = "", model_end_label: str = "") -> str:
        return "\n".join(f"{m['role']}> {m['content']}" for m in self.history if 'role' in m and 'content' in m)

    def raw_history(self) -> list:
        return self.history


def open_chat_with(fchat: FlashChat):
    user_message = input("user: ")
    while user_message != "stop":
        response = fchat.prompt(user_message)
        print(f"flash: {response}")
        user_message = input("user: ")

if __name__ == '__main__':
    bot1 = FlashChat()
    print(open_chat_with(bot1))
