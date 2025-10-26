from typing import List, TypedDict, Callable, Tuple
import re
import json

import general_chat_api as genapi

print("tooled_llm.py")

class Toolwrapper:
    """
    Callable[[List[str]], Tuple[bool, str]]
    Tools should always take a single list as their argument
    Tools should respond with a tuple (urgent: bool, response: str)
        when urgent is True, the LLM will be given the response right away
        when urgent is False, the response will go in the unimportant message queue for later
        urgent should normally be True for actions
    """
    def __init__(self, name: str, action: Callable[[List[str]], Tuple[bool, str]], manual: str):
        self.name = name
        self.action: Callable[[List[str]], Tuple[bool, str]] = action
        self.manual = manual


class ToolLLM:
    def __init__(self,
                 directions: str = "",
                 tool_objects: List[Toolwrapper] = None,
                 model: str = genapi.default_model,
                 action_prompt: str = "",
                 debug: bool = False):
        self.debug = debug
        self.response_instructions = """
            OUTPUT FORMAT REQUIREMENTS:
            Your response MUST strictly follow this two-part structure:
            PART 1: THINKING PROCESS
            - Begin your response with your step-by-step reasoning and plan.
            - Detail the inputs received, your interpretation, and the sequence of actions you intend to take and why.
            - Review the rules and guidelines associated with your actions and how you should follow them.
            - Include what actions you won't be taking, or why you will be waiting before calling a certain action.
            - End your thoughts with a clear plan of what you will be doing and why
            - Think for as long as you need to
            - Do not write any JSON in your thoughts
            - This section MUST come before any JSON code.
            PART 2: JSON ACTION LIST
            - Following your thinking process, provide the JSON list containing the actions to be executed.
            - Arguments should ALWAYS be passed as strings
            - You may perform multiple actions in the same json list
            - Be sure not to leave trailing commas in side of json lists.
            - If no actions are required, end with an empty list: `[]`
            - This JSON block MUST be the absolute final part of your response. No text should follow it.
            - You must follow this exact Json format, your json list MUST start and end with the word 'JSON' in all caps directly attached to the list, like 'JSON[]JSON'
            - example json format: 
            JSON[
                { "action": "action name", "args": ["argument1", "argument2", "argument3"] },
                { "action": "action name", "args": ["argument1"] },
                { "action": "action name", "args": [] },
            ]JSON
        """

        self.directions: str = directions
        self.tool_instructions: str = ""

        self.unimportant_messages: List[str] = []

        self.tools: TypedDict[str, Toolwrapper] = {}
        if tool_objects is not None:
            for tool in tool_objects:
                self.tools[tool.name] = tool
                self.tool_instructions = f"{self.tool_instructions}{tool.manual}\n"

        initial_prompt = f"""
            Primary directions:
            {directions}

            {self.response_instructions}

            Available tools:
            {self.tool_instructions}

            You may not preform any actions on this turn. 
            Instructions are complete. Acknowledge your instructions and wait patiently.
        """

        self.llm = genapi.FlashChat(initial_prompt, model)

        if action_prompt:
            self.prompt(action_prompt)

    def seperate_llm_response(self, text: str) -> (str, list):
        try:
            # Extract everything before the JSON marker as 'thought'
            prematch = re.search(r'^(.*?)JSON\[', text, re.DOTALL)
            thought = prematch.group(1).strip() if prematch else ''

            # Extract JSON-like portion specifically inside aaaBISON...aaa
            postmatch = re.search(r'JSON(\[.*?\])JSON', text, re.DOTALL)
            if not postmatch:
                raise ValueError('No JSON list found between aaaBISON...aaa markers.')

            json_str = postmatch.group(1).strip()

            # Validate JSON and parse
            data = json.loads(json_str)

            if not (isinstance(data, list) and all(isinstance(item, dict) for item in data)):
                if isinstance(data, list):
                    inner_types = [type(item).__name__ for item in data]
                    raise TypeError(f"Expected a list[dict], but got: list containing {inner_types}")
                else:
                    raise TypeError(f"Expected a list[dict] but got {type(data).__name__}")

            return thought, data
        except Exception as e:
            print(f"LLM message failed to parse. Asking them to send it again.")
            print(f"\n'{text}'")
            self.prompt(f"""
                Your last message failed to be parsed.  
                Error -> '{e}'
                Send it again according to the response instructions so that it can be parsed properly.
                You should not have any brackets '[', ']' in your thoughts.
                Be sure not to leave trailing commas in side of json lists.
                {self.response_instructions}
            """)
            return "", []

    def preform_action(self, action_name: str, arguments: List[str]) -> str:
        print(f"    {action_name}({arguments})")
        tool: Toolwrapper = self.tools.get(action_name)

        if tool is None:
            return f"error: action '{action_name}' was not found"

        urgent, response = tool.action(arguments)

        if response:
            response = f"{action_name}: {response}"

        if urgent:
            return response

        self.unimportant_messages.append(response)
        return ""

    def load_unimportant_messages(self) -> str:
        if len(self.unimportant_messages) == 0:
            return ""
        messages = ""
        for text in self.unimportant_messages:
            messages = f"{messages}{text}\n"
        self.unimportant_messages = []
        return f"{messages}\n"

    def prompt(self, user_prompt: str):
        print(f"(DEBUG) ToolLLM.prompt called with user_prompt: {user_prompt}") if self.debug else 0

        # Load unimportant messages and combine with user prompt
        unimportant_messages = self.load_unimportant_messages()
        full_prompt = f"{unimportant_messages}{user_prompt}"
        print(f"Full prompt to LLM: {full_prompt}") if self.debug else 0

        # Get response from LLM
        llm_response: str = self.llm.prompt(full_prompt)
        print(f"LLM response received, length: {len(llm_response)}") if self.debug else 0

        thoughts: str
        data: list = None

        # Parse the response
        print("Parsing LLM response") if self.debug else 0
        thoughts, data = self.seperate_llm_response(llm_response)
        print(f"Parsed thoughts (first 100 chars): {thoughts[:100] if thoughts else 'None'}") if self.debug else 0
        print(f"Parsed data: {data}") if self.debug else 0

        # Process actions
        while len(data):
            print(f"Processing {len(data)} actions") if self.debug else 0

            if isinstance(data, dict):
                print("Converting dict to list") if self.debug else 0
                data = [data]

            prompt: str = ""
            for block_index, block in enumerate(data):
                print(f"Processing action block {block_index}: {block}") if self.debug else 0
                action = block.get("action")

                if action is None:
                    print(f"No action in block {block_index}, skipping") if self.debug else 0
                    continue

                arguments: List[str] = block.get("args", [])
                print(f"Action: {action}, Arguments: {arguments}") if self.debug else 0

                result = self.preform_action(action, arguments)
                print(f"Action result: {result}") if self.debug else 0

                if result != "":
                    prompt = f"{prompt}{result}\n"
                    print(f"Updated prompt: {prompt}") if self.debug else 0

            if prompt == "":
                print("No prompt generated, breaking loop") if self.debug else 0
                break

            print(f"Sending follow-up prompt to LLM: {prompt}") if self.debug else 0
            llm_response = self.llm.prompt(f"{self.load_unimportant_messages()}{prompt}")
            print(f"Follow-up LLM response received, length: {len(llm_response)}") if self.debug else 0

            thoughts, data = self.seperate_llm_response(llm_response)
            print(f"Follow-up parsed thoughts (first 100 chars): {thoughts[:100] if thoughts else 'None'}") if self.debug else 0
            print(f"Follow-up parsed data: {data}") if self.debug else 0

        print("ToolLLM.prompt completed") if self.debug else 0


if __name__ == '__main__':
    def send_message(messages: List[str]) -> Tuple[bool, str]:
        if len(messages) == 0:
            return True, "error: empty message list"

        for msg in messages:
            lines = msg.split('\n')
            for line in lines:
                print(f"   {line}")
        return False, "Message sent"


    tutor_tools: List[Toolwrapper] = [
        Toolwrapper("send_message",
                    send_message, """
                Action name: "send_message"
                Arguments: list of messages
                Purpose: This tool is the only way you are able to communicate with users. The tool sends 1 or more messages to the user. Break up long messages with '\\n'.
                Returns: conformation with Success or Fail
                """)
        ]

    Tutor: ToolLLM = ToolLLM(tool_objects=tutor_tools, directions=f"You are a Tutor, use your tools to talk to the student and help them.")

    user_message = input("user: ")
    while user_message != "stop":
        Tutor.prompt(user_message)
        user_message = input("user: ")

