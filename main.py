import io
import os
from fastapi import FastAPI, File, UploadFile,Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from services.assistant import Assitant
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Initialize the Assistant object
agent = Assitant()
client = OpenAI()

# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

@app.post("/stream/text")
async def stream_output(input_data: dict = {
    'query': 'query',
    'session_id': 'session_id'
    }):
    return StreamingResponse(agent.get_response(query=input_data.get('query'), session_id=input_data.get('session_id')), media_type="text/plain")


@app.post("/stream/audio")
async def process_audio(file: UploadFile = File(...), input_data: dict ={
    'session_id': 'session_id'
    }):
    audio_data = await file.read()

    #  temporary save the file to disk
    with open(f"{session_id}temp.wav", "wb") as f:
        f.write(audio_data)

    transcription = client.audio.transcriptions.create(
        model="whisper-1", 
        file=open(f"{session_id}temp.wav", "rb")
        )
    if transcription.text:
        response = agent.get_response(query=transcription.text, session_id=input_data.get('session_id'), audio=True)

    return StreamingResponse(response) 