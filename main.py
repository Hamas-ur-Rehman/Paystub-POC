import json
import os
import asyncio
import websockets
from datetime import datetime, timedelta
from fastapi import FastAPI, Query,WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse,JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from services.history_service import HistoryService
from services.utils import *

from services.assistant import Assitant
from services.logger import log
from services.mongo_service import MongoDBService
from realtime_sessions.configure import session_update
from dotenv import load_dotenv
load_dotenv()

LOG_EVENT_TYPES = [
    'error', 
    'response.content.done', 
    'rate_limits.updated',
    'response.done', 
    'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 
    'input_audio_buffer.speech_started',
    'session.created'
]


# Initialize FastAPI app
app = FastAPI()
history_service = HistoryService()


# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

@app.post("/stream/text")
def stream_output(input_data: dict = {
    'query': 'query',
    'session_id': 'session_id'
    }):
    try: 
        agent = Assitant()
        return StreamingResponse(agent.get_response(query=input_data.get('query'), session_id=input_data.get('session_id')), media_type="text/plain")
    except Exception as e:
        log.error(e)
        return {"error": "An error occurred"}
 

@app.websocket("/audio_stream")
async def handle_media_stream(websocket: WebSocket):
    log.info('Client Connected')
    timeout_duration = timedelta(minutes=14)
    await websocket.accept()
    async with websockets.connect(
        'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
        extra_headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as openai_ws:
        session_id = None
        history = []
        is_initialize = False

        async def receive_from_client():
            nonlocal session_id
            nonlocal history
            nonlocal is_initialize
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data:
                        log.info(f"Received message: {message[:100]}")
                        log.info(f"Session ID: {data.get('session_id')}")
                        log.info(type(data.get('audio_bytes')))
                    
                    if data.get('audio_bytes') and data.get('session_id'):
                        session_id = data.get('session_id')
                        if not is_initialize:
                            await initialize_session(openai_ws,session_id)
                            is_initialize = True
                        
                        raw_audio = np.array(data['audio_bytes'], dtype=np.float32)
                        if len(raw_audio.shape) > 1:
                            raw_audio = raw_audio[:, 0]

                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": base64_encode_audio(raw_audio)
                        }
                        await openai_ws.send(json.dumps(audio_append))

            except WebSocketDisconnect:
                if session_id:
                    history_service.insert_chat(session_id=session_id, history=history)
                log.info('Client Disconnected')
                if openai_ws.open:
                    await openai_ws.close()

        async def send_to_client():
            nonlocal session_id
            nonlocal history

            try:
                async for openai_message in openai_ws:
                    message = json.loads(openai_message)
                    log.info(f"{message.get('type')} - {message.get('event_id')}")

                    if message.get("type") == "response.content_part.added":
                        await websocket.send_text(json.dumps({"end": False,"new":True}))
                    
                    elif  message.get("type") == "response.created":
                        
                        # Send interrupt message to OpenAI
                        interrupt_message = {
                            "type": "input_audio_buffer.clear"
                        }
                        await openai_ws.send(json.dumps(interrupt_message))

                    elif message.get("type") == "response.audio.delta":
                        await websocket.send_text(json.dumps({"audio": base64.b64encode(base64.b64decode(message['delta'])).decode('utf-8')}))

                    elif message.get("type") == 'response.audio_transcript.delta':
                        await websocket.send_text(json.dumps({"transcript": message.get("delta")}))

                    elif message.get("type") == 'conversation.item.input_audio_transcription.completed':
                        history.append(get_valid_json_history(message.get("transcript"),"user"))  
                     
                    elif message.get("type") == 'response.audio_transcript.done':
                        history.append(get_valid_json_history(message.get("transcript"),"assistant"))  

                    elif message.get("type") == 'response.function_call_arguments.done':
                        tool_call_id = message.get("call_id")
                        tool_name = message.get("name")
                        tool_args = message.get("arguments")
                        await websocket.send_text(json.dumps({"function_name": tool_name, "inputs": tool_args}))
                        _ = get_valid_json_history(tool_call_id,"function_call")
                        history.append(_)
                        # Send the response to the assistant
                        await openai_ws.send(_)

                        await openai_ws.send(json.dumps({
                            "type": "response.create",
                            "response": {
                                    "modalities": ["text", "audio"],
                                    "instructions": "Please tell the user that the tool has been successfully executed in a cool michael jackson voice",
                                }
                        }))
                    
                    elif message.get("type") == "error":
                        log.warning(f"warning in response: {message}")

                    elif message.get("type") == "response.done":
                        if session_id:
                            history_service.insert_chat(session_id=session_id, history=history)
                        await websocket.send_text(json.dumps({"end": True}))

            except Exception as e:
                log.error(f"Error in sending audio delta back to client: {e}",exc_info=True)

        async def close_after_timeout():
            # Wait for 13 minutes
            await asyncio.sleep(timeout_duration.total_seconds())
            if websocket.client_state.name != "CLOSED":
                await websocket.close()
                await openai_ws.close()
                log.info("Connection closed due to timeout")
            


        await asyncio.gather(receive_from_client(), send_to_client(), close_after_timeout())

async def initialize_session(openai_ws,session_id):
    session_history = history_service.fetch_chats(session_id=session_id)
    await openai_ws.send(json.dumps(session_update))
    if session_history:
        session_update["session"]["instructions"] = session_update["session"]["instructions"] + "\n--------------\n\n" + f"This is the conversation history {session_history}\n\n"
        # session_history = list(set(session_history))
        # log.info(f"Session history size: {len(session_history)}")
        # for item in session_history:
        #     try:
        #         if json.loads(item):
        #             await openai_ws.send(item)
        #     except Exception as _:
        #         pass
def get_valid_json_history(message,role):
    if role == "user":
        return """{
                    "type": "conversation.item.create",
                    "previous_item_id": null,
                    "item": {
                        "type": "message",
                        "status": "completed",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": \'"""+message+"""\",
                            }
                        ]
                    }
                }"""
    elif role == "assistant":
        return """{
                    "type": "conversation.item.create",
                    "previous_item_id": null,
                    "item": {
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": \""""+message+"""\",
                            }
                        ]
                    }
                }"""
    elif role == "function_call":
        return """{
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                            "call_id": \""""+message+"""\",
                            "output": "{'success': 'true'}"
                        }
                        }"""