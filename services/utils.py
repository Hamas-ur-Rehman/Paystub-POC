import base64
import numpy as np

def is_base64(data: str) -> bool:
    try:
        base64.b64decode(data, validate=True)
        return True
    except (ValueError, TypeError):
        return False


# # Converts Float32Array of audio data to PCM16 byte array
def float_to_16bit_pcm(float32_array):
    pcm16_array = (np.clip(float32_array, -1, 1) * 32767).astype(np.int16)
    return pcm16_array.tobytes()

# # Converts Float32Array to base64-encoded PCM16 data
def base64_encode_audio(float32_array):
    pcm16_bytes = float_to_16bit_pcm(float32_array)
    return base64.b64encode(pcm16_bytes).decode("utf-8")

