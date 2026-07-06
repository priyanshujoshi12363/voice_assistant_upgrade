import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

import config
from wakeword import WakeWord
from stt import STT
from llm import LLM
from tts import TTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("server")

app = FastAPI()
pool = ThreadPoolExecutor(max_workers=2)
pipeline_lock = asyncio.Lock()

FRAME_MS = config.FRAME_SAMPLES / config.SAMPLE_RATE * 1000

stt = None
tts = None


@app.on_event("startup")
def load_models():
    global stt, tts
    log.info("loading whisper (%s)", config.WHISPER_MODEL)
    stt = STT(config.WHISPER_MODEL, config.WHISPER_COMPUTE)
    try:
        log.info("loading piper")
        tts = TTS(config.PIPER_MODEL, config.PIPER_CONFIG, config.SAMPLE_RATE)
    except Exception as exc:
        tts = None
        log.warning("piper unavailable, transcript-only mode: %s", exc)
    log.info("models ready")


@app.get("/")
def health():
    return {"status": "ok"}


def _rms(frame):
    if frame.size == 0:
        return 0.0
    f = frame.astype(np.float32)
    return float(np.sqrt(np.mean(f * f)))


class Session:
    def __init__(self):
        self.wake = WakeWord(config.WAKEWORD_MODELS, config.WAKEWORD_THRESHOLD)
        self.llm = LLM(
            config.OLLAMA_BASE_URL,
            config.OLLAMA_API_KEY,
            config.OLLAMA_MODEL,
            config.SYSTEM_PROMPT,
        )
        self.mode = "listen"
        self.leftover = np.zeros(0, dtype=np.int16)
        self._reset_capture()

    def _reset_capture(self):
        self.capture = []
        self.elapsed = 0.0
        self.silence = 0.0
        self.speech = 0.0
        self.heard = False

    def feed(self, samples):
        self.leftover = np.concatenate([self.leftover, samples])
        command = None
        while self.leftover.size >= config.FRAME_SAMPLES:
            frame = self.leftover[: config.FRAME_SAMPLES]
            self.leftover = self.leftover[config.FRAME_SAMPLES :]
            if self.mode == "listen":
                if self.wake.detect(frame):
                    self.mode = "capture"
                    self._reset_capture()
            else:
                self.capture.append(frame)
                self.elapsed += FRAME_MS
                if _rms(frame) >= config.SILENCE_RMS:
                    self.heard = True
                    self.speech += FRAME_MS
                    self.silence = 0.0
                else:
                    self.silence += FRAME_MS
                done = (
                    self.heard
                    and self.speech >= config.MIN_SPEECH_MS
                    and self.silence >= config.END_SILENCE_MS
                ) or self.elapsed >= config.MAX_COMMAND_MS
                if done:
                    command = (
                        np.concatenate(self.capture)
                        if self.capture
                        else np.zeros(0, dtype=np.int16)
                    )
                    self.mode = "listen"
                    self.wake.reset()
                    break
        return command


async def send_audio(ws, samples):
    await ws.send_text(json.dumps({"type": "play_start"}))
    data = np.asarray(samples, dtype=np.int16).tobytes()
    step = config.FRAME_SAMPLES * 2
    for off in range(0, len(data), step):
        await ws.send_bytes(data[off : off + step])
    await ws.send_text(json.dumps({"type": "play_end"}))


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    loop = asyncio.get_event_loop()
    session = await loop.run_in_executor(pool, Session)
    log.info("client connected")
    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                break
            data = message.get("bytes")
            if not data:
                continue
            if len(data) % 2:
                data = data[:-1]
            samples = np.frombuffer(data, dtype=np.int16)
            command = await loop.run_in_executor(pool, session.feed, samples)
            if command is None or command.size == 0:
                continue
            async with pipeline_lock:
                text = await loop.run_in_executor(pool, stt.transcribe, command)
                log.info("transcript: %r", text)
                if not text:
                    continue
                await ws.send_text(json.dumps({"type": "transcript", "text": text}))
                reply = await loop.run_in_executor(pool, session.llm.ask, text)
                log.info("reply: %r", reply)
                if tts is not None:
                    audio = await loop.run_in_executor(pool, tts.synthesize, reply)
                    await send_audio(ws, audio)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.exception("session error: %s", exc)
    finally:
        log.info("client disconnected")
