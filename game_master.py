from typing import List, TypedDict, Callable, Tuple
import tooled_llm
import InventoryStoreSystem as inv

default_start_up_instructions = """
    This is your oppurtinty to setup the game. Make any tools calls you need to now 
    to start the game. You should also think about and craft your initial message to the player and then send it to them.
    """.strip()


class Gamemaster:
    def __init__(self, story, start_up_instructions=default_start_up_instructions):
        """
        Player info
            items (name, quanity, description)
            location

        World info
            Let it access additonal information for places in the world
            could be a vector database

        Add tools like notes, reminders upon action,
        """
        self.start_up_instructions = start_up_instructions
        tools = inv.build_tools()

        def send_message(messages: List[str]) -> Tuple[bool, str]:
            if len(messages) == 0:
                return True, "error: empty message list"

            for msg in messages:
                lines = msg.split('\n')
                for line in lines:
                    print(f"GM: {line}")
            return False, "Message sent"

        msgtool = tooled_llm.Toolwrapper("send_message",
                    send_message, """
                        Action name: "send_message"
                        Arguments: list of messages
                        Purpose: This tool is the only way you are able to communicate with the player. The tool sends 1 or more messages to the player. Break up long messages with '\\n'.
                        Returns: conformation with Success or Fail
                        """)

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

        self.master = tooled_llm.ToolLLM(instructions, tools)

    def game_loop(self):
        self.master.prompt(self.start_up_instructions)

        user_message = input("Player: ")
        while user_message != "stop":
            self.master.prompt(user_message)
            user_message = input("Player: ")














