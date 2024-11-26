import json
import base64
import os
import websocket
import websockets
from fastapi import FastAPI, Query,WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from services.assistant import Assitant
from services.logger import log
from services.history_service import HistoryService
from realtime_sessions.configure import session_update
from services.utils import *
import numpy as np
from dotenv import load_dotenv
load_dotenv()



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
async def audio_stream(websocket_: WebSocket):
    await websocket_.accept()
    try:
        while True:
            data = await websocket_.receive_text()
            audio_chunk = json.loads(data)
            raw_audio = audio_chunk.get("audio_bytes")
            session_id = audio_chunk.get("session_id")
            
            try:
                raw_audio = np.array(raw_audio, dtype=np.float32)
            except Exception as e:
                await websocket_.send_text(json.dumps({"error": "An error occurred while processing the audio"}))
                log.error(e, exc_info=True)
                return
            log.info(f"Audio chunk recieved: {raw_audio[:10]}")
            # Handle multi-channel audio by taking the first channel
            if len(raw_audio.shape) > 1:
                raw_audio = raw_audio[:, 0]

            base64_audio = base64_encode_audio(raw_audio)

            if base64_audio:
                url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
                headers = {
                    "Authorization": "Bearer " + os.getenv("OPENAI_API_KEY"),
                    "OpenAI-Beta": "realtime=v1",
                }
                async with websockets.connect(uri=url,extra_headers=headers) as internal_socket:
                    history = []
                    try:
                        log.info("Fetching session history")
                        session_history = history_service.fetch_chats(session_id=session_id)
                        if len(session_history) > 0:
                            session_update['session']['instructions'] = session_update['session']['instructions'] +  f"\n\nThis is the entire history of the conversation so far {json.dumps(session_history)}"
                        await internal_socket.send(json.dumps(session_update))

                        log.info("Session history fetched")
                    except Exception as e:
                        log.error(e)

                    await internal_socket.send(json.dumps({ "type": "input_audio_buffer.append","audio": f"{base64_audio}"}))
                    await internal_socket.send(json.dumps({"type": "input_audio_buffer.commit"}))
                    await internal_socket.send(json.dumps({"type": "response.create"}))
                    previous_type = None
                    chunk = 0

                    while True:
                        try:
                            if chunk == 0:
                                await websocket_.send_text(json.dumps({"transcript": "\n","new": True}))
                                chunk += 1
                            response = await internal_socket.recv()
                            message = json.loads(response)
                            log.info(message.get("type"))
                            if message.get("type") == "response.audio.delta":
                                await websocket_.send_text(json.dumps({"audio": message.get("delta")}))

                            elif message.get("type") == 'response.audio_transcript.delta':
                                await websocket_.send_text(json.dumps({"transcript": message.get("delta")}))

                            elif message.get("type") == 'conversation.item.input_audio_transcription.completed':
                                data =  {"role": "user", "content": message.get("transcript")}
                                if previous_type == "response.function_call_arguments.done":
                                    previous_type = None
                                    history.insert(-1,data)
                                else:
                                    history.append(data)    

                            elif message.get("type") == 'response.audio_transcript.done':
                                history.append({"role": "assistant", "content": message.get("transcript")})  

                            elif message.get("type") == 'response.function_call_arguments.done':
                                tool_call_id = message.get("call_id")
                                tool_name = message.get("name")
                                tool_args = message.get("arguments")
                                await websocket_.send_text(json.dumps({"function_name": tool_name, "inputs": tool_args}))
                                history.append({"role": "assistant", "content": f"Executing {tool_name} with arguments {tool_args}","output": {"success": True}})

                                # Send the response to the assistant
                                await internal_socket.send(json.dumps({
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                            "call_id": tool_call_id,
                                            "output": {"success": True}
                                        }
                                }))

                                await internal_socket.send(json.dumps({
                                    "type": "response.create",
                                    "response": {
                                            "modalities": ["text", "audio"],
                                            "instructions": "Please tell the user that the tool has been successfully executed in a cool michael jackson voice",
                                        }
                                }))

                                previous_type = "response.function_call_arguments.done"

                            elif message.get("type") == "error":
                                pass
                            
                            elif message.get("type") == "response.done":
                                if previous_type == "response.function_call_arguments.done":
                                    pass
                                else:
                                    history_service.insert_chat(session_id=session_id,history=history)
                                    break


                        except Exception as e:
                            log.error(e)
                        except websockets.ConnectionClosed:
                            break


    except WebSocketDisconnect:
        log.error("Client disconnected")
        return