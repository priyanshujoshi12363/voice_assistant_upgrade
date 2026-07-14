import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve(value):
    if not value:
        return value
    return value if os.path.isabs(value) else os.path.join(BASE_DIR, value)


def _model_path(env_key, default_rel, is_dir):
    check = os.path.isdir if is_dir else os.path.isfile
    bundled = os.path.join(BASE_DIR, default_rel)
    value = _resolve(os.getenv(env_key, default_rel))
    if check(value):
        return value
    return bundled if check(bundled) else value


SAMPLE_RATE = 16000
FRAME_SAMPLES = 1280

SILENCE_RMS = float(os.getenv("SILENCE_RMS", "500"))
END_SILENCE_MS = int(os.getenv("END_SILENCE_MS", "800"))
MAX_COMMAND_MS = int(os.getenv("MAX_COMMAND_MS", "12000"))
MIN_SPEECH_MS = int(os.getenv("MIN_SPEECH_MS", "300"))

WHISPER_MODEL = _model_path("WHISPER_MODEL", "models/faster-whisper-tiny.en", True)
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b-cloud")

PIPER_MODEL = _model_path("PIPER_MODEL", "voices/en_US-lessac-medium.onnx", False)
PIPER_CONFIG = _model_path("PIPER_CONFIG", "voices/en_US-lessac-medium.onnx.json", False)

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful voice assistant. Answer in one or two short spoken sentences.",
)
