import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve(value):
    if not value:
        return value
    candidate = value if os.path.isabs(value) else os.path.join(BASE_DIR, value)
    return candidate if os.path.exists(candidate) else value


SAMPLE_RATE = 16000
FRAME_SAMPLES = 1280

SILENCE_RMS = float(os.getenv("SILENCE_RMS", "500"))
END_SILENCE_MS = int(os.getenv("END_SILENCE_MS", "800"))
MAX_COMMAND_MS = int(os.getenv("MAX_COMMAND_MS", "12000"))
MIN_SPEECH_MS = int(os.getenv("MIN_SPEECH_MS", "300"))

WHISPER_MODEL = _resolve(os.getenv("WHISPER_MODEL", "models/faster-whisper-tiny.en"))
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b-cloud")

PIPER_MODEL = _resolve(os.getenv("PIPER_MODEL", "voices/en_US-lessac-medium.onnx"))
PIPER_CONFIG = _resolve(os.getenv("PIPER_CONFIG", "voices/en_US-lessac-medium.onnx.json"))

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful voice assistant. Answer in one or two short spoken sentences.",
)
