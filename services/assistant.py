import os 
import json
from dotenv import load_dotenv
from openai import OpenAI
from .logger import log
from openai.types.beta.threads import Text, TextDelta
from openai.types.beta.threads.runs import ToolCall, ToolCallDelta
from openai import AssistantEventHandler
from typing_extensions import override

load_dotenv()

# EventHandler class to define how to handle events in the response stream.

def handle_requires_action(data):
    tool_outputs = []
    tools_to_run = []
    
    for tool in data.required_action.submit_tool_outputs.tool_calls:
        tool_outputs.append(
                {"tool_call_id": tool.id, "output": "{success:true}"}
            )
        tools_to_run.append(
            {
                "function_name": tool.function.name,
                "inputs": tool.function.arguments,
            }
        )
    
    return tool_outputs, tools_to_run
    
class Assitant:
    def __init__(self):
        self.thread_log = "./thread_log.json"
        self.client = OpenAI()

        log.info("Assistant Initialized")

    def get_response(self, query , session_id=None, audio=False):
        log.info("Getting response from assistant")
        try:
            log.info(f"Query: {query}")
            if session_id is not None:
                log.info(f"Session ID provided: {session_id}")
                thread = self.check_and_get_thread_id(session_id)
                if thread is not None:
                    log.info(f"Thread ID found for session ID '{session_id}': {thread}")
                    self.__add_message_in_thread(thread, query)
                else:
                    log.info(f"No Thread ID found for session ID '{session_id}'")
                    thread = self.client.beta.threads.create()
                    self.__add_message_in_thread(thread.id, query)
                    self.save_session_thread(session_id, thread.id)
                    thread = thread.id

                yield from self.__data_delivery(thread=thread, audio=audio)
                
                
                
        except Exception as e:
            log.error(e)

    def __data_delivery(self,thread, audio=False):
        with self.client.beta.threads.runs.stream(
                    thread_id=thread,
                    assistant_id=os.getenv("ASSISTANT_ID"),
                ) as stream:
                    for event in stream:
                        log.info(f"{event.event}")
                        if event.event == "thread.message.delta":
                            yield event.data.delta.content[0].text.value
                        elif event.event == "thread.run.requires_action":
                            run_id = event.data.id
                            tool_outputs, tools_to_run = handle_requires_action(event.data)
                            yield "\n\n```FUNCTION_CALL_START\n\n"
                            yield json.dumps(tools_to_run,indent=4)
                            yield "\n\n```FUNCTION_CALL_END\n\n"

                            if tool_outputs:
                                with self.client.beta.threads.runs.submit_tool_outputs_stream(
                                    thread_id=thread,
                                    run_id=run_id,
                                    tool_outputs=tool_outputs,
                                ) as stream:
                                    log.info("--------Tool Outputs Submitted------")
                                    for internal_event in stream:
                                        log.info(f"{internal_event.event}")
                                        if internal_event.event ==  "thread.message.delta":
                                            yield internal_event.data.delta.content[0].text.value

                    if not audio:
                        yield from stream.text_deltas
                    else:
                        chunk_combined = ''
                        for i in stream.text_deltas:
                            if i.endswith("\n") or i.endswith("\n\n") or i.endswith("."):
                                response = self.client.audio.speech.create(
                                    model="tts-1",
                                    voice="alloy",
                                    input=chunk_combined,
                                )
                                for audio_bytes in response.iter_bytes():
                                    yield audio_bytes

                                chunk_combined = ''
                            else:
                                chunk_combined += i

    def __add_message_in_thread(self,thread_id, query):
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=query
            )

    def check_and_get_thread_id(self, session_id):
        if not os.path.exists(self.thread_log):
            return None

        try:
            with open(self.thread_log, 'r') as file:
                # Load the JSON data from the file
                thread_dict = json.load(file)

            # Check if the session ID exists in the dictionary
            return thread_dict.get(session_id, None)

        except json.JSONDecodeError as e:
            log.info(f"Error decoding JSON from the file: {e}")
            return None

    def save_session_thread(self, session_id, thread_id):
        data = {}

        # Check if the file exists
        if os.path.exists(self.thread_log):
            try:
                # Read existing data from the file
                with open(self.thread_log, 'r') as file:
                    data = json.load(file)
            except json.JSONDecodeError as e:
                log.info(f"Error decoding JSON from the file: {e}")
                data = {}

        # Update the dictionary with the new session ID and thread ID
        data[session_id] = thread_id

        # Write the updated data back to the file
        with open(self.thread_log, 'w') as file:
            json.dump(data, file, indent=4)

        log.info(f"Session ID '{session_id}' with Thread ID '{thread_id}' saved successfully.")



