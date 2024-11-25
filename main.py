import json
import os
import websocket
import websockets
from fastapi import FastAPI, Query,WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from services.assistant import Assitant
from services.logger import log
from services.mongo_service import MongoDBService
from realtime_sessions.configure import session_update
from dotenv import load_dotenv
load_dotenv()



# Initialize FastAPI app
app = FastAPI()
mongo_service = MongoDBService()


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
            data_buffer = []
            data = await websocket_.receive_text()
            audio_chunk = json.loads(data)
            base64_audio = audio_chunk.get("audio_bytes")
            session_id = audio_chunk.get("session_id")

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
                        session_history = mongo_service.fetch_chats(session_id=session_id)
                        if session_history:
                            session_update['session']['instructions'] = session_update['session']['instructions'] +  f"\n\nThis is the entire history of the conversation so far {json.dumps(session_history)}"
                        await internal_socket.send(json.dumps(session_update))

                        log.info("Session history fetched")
                    except Exception as e:
                        log.error(e)

                    await internal_socket.send(json.dumps({ "type": "input_audio_buffer.append","audio": f"{base64_audio}"}))
                    await internal_socket.send(json.dumps({"type": "input_audio_buffer.commit"}))
                    await internal_socket.send(json.dumps({"type": "response.create"}))
                    previous_type = None

                    while True:
                        try:
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
                                    mongo_service.insert_chat(session_id=session_id,history=history)
                                    break


                        except Exception as e:
                            log.error(e)
                        except websockets.ConnectionClosed:
                            break


    except WebSocketDisconnect:
        log.error("Client disconnected")
        return