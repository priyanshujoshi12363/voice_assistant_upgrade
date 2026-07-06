import os
from dotenv import load_dotenv

load_dotenv()

SAMPLE_RATE = 16000
FRAME_SAMPLES = 1280

WAKEWORD_MODELS = os.getenv("WAKEWORD_MODELS", "hey_jarvis")
WAKEWORD_THRESHOLD = float(os.getenv("WAKEWORD_THRESHOLD", "0.5"))

SILENCE_RMS = float(os.getenv("SILENCE_RMS", "500"))
END_SILENCE_MS = int(os.getenv("END_SILENCE_MS", "800"))
MAX_COMMAND_MS = int(os.getenv("MAX_COMMAND_MS", "12000"))
MIN_SPEECH_MS = int(os.getenv("MIN_SPEECH_MS", "300"))

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b-cloud")

PIPER_MODEL = os.getenv("PIPER_MODEL", "voices/en_US-lessac-medium.onnx")
PIPER_CONFIG = os.getenv("PIPER_CONFIG", "voices/en_US-lessac-medium.onnx.json")

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful voice assistant. Answer in one or two short spoken sentences.",
)
