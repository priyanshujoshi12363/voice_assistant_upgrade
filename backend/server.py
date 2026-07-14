import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import asyncio
import json
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

import config
from stt import STT
from llm import LLM
from tts import TTS

app = FastAPI()
pool = ThreadPoolExecutor(max_workers=2)
pipeline_lock = asyncio.Lock()

FRAME_MS = config.FRAME_SAMPLES / config.SAMPLE_RATE * 1000

stt = None
tts = None


@app.on_event("startup")
def load_models():
    global stt, tts
    stt = STT(config.WHISPER_MODEL, config.WHISPER_COMPUTE)
    try:
        tts = TTS(config.PIPER_MODEL, config.PIPER_CONFIG, config.SAMPLE_RATE)
    except Exception:
        tts = None


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
        self.llm = LLM(
            config.OLLAMA_BASE_URL,
            config.OLLAMA_API_KEY,
            config.OLLAMA_MODEL,
            config.SYSTEM_PROMPT,
        )
        self.mode = "idle"
        self.leftover = np.zeros(0, dtype=np.int16)
        self.preroll = deque(maxlen=3)
        self._reset_capture()

    def _reset_capture(self):
        self.capture = []
        self.elapsed = 0.0
        self.silence = 0.0
        self.speech = 0.0

    def feed(self, samples):
        self.leftover = np.concatenate([self.leftover, samples])
        command = None
        while self.leftover.size >= config.FRAME_SAMPLES:
            frame = self.leftover[: config.FRAME_SAMPLES]
            self.leftover = self.leftover[config.FRAME_SAMPLES :]
            level = _rms(frame)
            if self.mode == "idle":
                self.preroll.append(frame)
                if level >= config.SILENCE_RMS:
                    self._reset_capture()
                    self.capture.extend(self.preroll)
                    self.preroll.clear()
                    self.speech = FRAME_MS
                    self.elapsed = FRAME_MS
                    self.mode = "capture"
            else:
                self.capture.append(frame)
                self.elapsed += FRAME_MS
                if level >= config.SILENCE_RMS:
                    self.speech += FRAME_MS
                    self.silence = 0.0
                else:
                    self.silence += FRAME_MS
                done = (
                    self.speech >= config.MIN_SPEECH_MS
                    and self.silence >= config.END_SILENCE_MS
                ) or self.elapsed >= config.MAX_COMMAND_MS
                if done:
                    command = (
                        np.concatenate(self.capture)
                        if self.capture
                        else np.zeros(0, dtype=np.int16)
                    )
                    self.mode = "idle"
                    self.preroll.clear()
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
            try:
                async with pipeline_lock:
                    text = await loop.run_in_executor(pool, stt.transcribe, command)
                    if not text:
                        continue
                    await ws.send_text(json.dumps({"type": "transcript", "text": text}))
                    reply = await loop.run_in_executor(pool, session.llm.ask, text)
                    await ws.send_text(json.dumps({"type": "reply", "text": reply}))
                    if tts is not None:
                        audio = await loop.run_in_executor(pool, tts.synthesize, reply)
                        await send_audio(ws, audio)
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
