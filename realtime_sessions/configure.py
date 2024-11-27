import json
from .prompt import INSTRUCTIONS

with open('./realtime_sessions/tools.json', 'r') as file:
    TOOLS = json.load(file)

session_update = {
    "type": "session.update",
    "session": {
        "modalities": ["text", "audio"],
        "instructions": INSTRUCTIONS,
        "voice": "alloy",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "turn_detection": {
            "type": "server_vad",
            "prefix_padding_ms": 3,
            "silence_duration_ms": 7
        },
        "tools":TOOLS ,
        "tool_choice": "auto",
        "temperature": 0.8,
    }
}
