<h1 align="center">🎙️ ESP32-S3 Voice Q&A Assistant</h1>

<p align="center">
  <b>You talk, it answers out loud.</b><br>
  A tiny ESP32-S3 becomes a voice device — the brains live on a FastAPI server you deploy to the cloud.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue.svg" alt="Python 3.11">
  <img src="https://img.shields.io/badge/FastAPI-WebSocket-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/ESP32--S3-Arduino-red.svg" alt="ESP32-S3">
  <img src="https://img.shields.io/badge/LLM-Ollama%20Cloud-black.svg" alt="Ollama Cloud">
  <img src="https://img.shields.io/badge/deploy-Render-46E3B7.svg" alt="Render">
</p>

---

The **ESP32-S3** is a dumb audio bridge over **WiFi WebSocket**: it streams
microphone audio up to the server and plays back the audio the server sends down.
All intelligence — wake word, speech-to-text, the LLM, and text-to-speech — runs
server-side.

```
ESP32 mic ─▶ WiFi WebSocket ─▶ [wake word] ─▶ [Whisper STT]
                                                    │
                                                    ▼
                                          [Ollama Cloud gpt-oss]
                                                    │
ESP32 speaker ◀── WebSocket ◀── [Piper TTS] ◀───────┘
```

## ✨ Features

- 🔊 **Voice in, voice out** — ask a question, hear a spoken answer.
- 🧠 **Cloud LLM** — `gpt-oss` via Ollama Cloud (OpenAI-compatible API).
- 🗣️ **Custom wake word** — runs on the server (openWakeWord), so any word works.
- ⚡ **CPU-only, no GPU** — faster-whisper with int8 quantization.
- 🌐 **Deploy anywhere** — one FastAPI service, one-click Render Blueprint.
- 🔌 **Persistent, self-healing WebSocket** — the ESP32 auto-reconnects.
- 📦 **Zero model wrangling** — Whisper and the Piper voice download on first boot.
- 🧪 **Test without hardware** — a PC-mic client talks to the server like the ESP32.

## 📑 Table of contents

- [How it works](#-how-it-works)
- [Project structure](#-project-structure)
- [Hardware & wiring](#-hardware--wiring)
- [Firmware](#-firmware)
- [Run the backend locally](#-run-the-backend-locally)
- [Test without an ESP32](#-test-without-an-esp32)
- [Deploy to Render](#-deploy-to-render)
- [Configuration](#-configuration)
- [WebSocket protocol](#-websocket-protocol)
- [Tuning](#-tuning)
- [Troubleshooting](#-troubleshooting--notes)

## 🔁 How it works

1. The ESP32 continuously streams 16 kHz / 16-bit / mono PCM from an I2S mic to
   the server over a persistent WebSocket.
2. The server runs **openWakeWord** on the stream. Nothing happens until the wake
   word fires.
3. After the wake word, the server captures audio until you stop talking (energy
   based silence detection), then transcribes it with **faster-whisper**.
4. The transcript goes to **Ollama Cloud** (`gpt-oss`), which returns a short,
   spoken-style answer.
5. **Piper** synthesizes the answer to PCM and streams it back over the same
   WebSocket. The ESP32 plays it and mutes its mic during playback to avoid
   feedback.

## 📂 Project structure

```
.
├── render.yaml                 Render Blueprint (deploys backend/)
├── .gitignore
├── firmware/
│   └── voice_bridge.ino        ESP32-S3 WiFi + WebSocket audio bridge
└── backend/
    ├── server.py               FastAPI app: GET / health + WS /ws pipeline
    ├── config.py               Loads settings from .env
    ├── wakeword.py             openWakeWord detection
    ├── stt.py                  faster-whisper transcription
    ├── llm.py                  Ollama Cloud chat (OpenAI-compatible)
    ├── tts.py                  Piper synthesis (+ auto voice download)
    ├── test_client.py          PC mic client to test without the ESP32
    ├── requirements.txt
    ├── Procfile
    ├── .env.example
    └── voices/                 Piper voice lands here (auto-downloaded)
```

## 🔌 Hardware & wiring

**Board:** ESP32-S3 SuperMini (PSRAM + two I2S peripherals)

<table>
<tr><th colspan="2">🎤 Mic — INMP441 (I2S in)</th><th colspan="2">🔈 Speaker — MAX98357A (I2S out)</th></tr>
<tr><td>VDD</td><td>3.3V</td><td>VIN</td><td>5V</td></tr>
<tr><td>GND</td><td>GND</td><td>GND</td><td>GND</td></tr>
<tr><td>SD</td><td>GPIO4</td><td>DIN</td><td>GPIO7</td></tr>
<tr><td>WS</td><td>GPIO5</td><td>BCLK</td><td>GPIO15</td></tr>
<tr><td>SCK</td><td>GPIO6</td><td>LRC</td><td>GPIO16</td></tr>
<tr><td>L/R</td><td>GND</td><td>+ / –</td><td>speaker</td></tr>
</table>

> 💡 Add a 470µF cap across MAX98357A VIN/GND if the board resets on loud playback.

## 🛠️ Firmware

1. Open `firmware/voice_bridge.ino` in the Arduino IDE.
2. Install the **esp32** board package (Espressif) and the **ArduinoWebsockets**
   library (by Gil Maimon).
3. Board: **ESP32S3 Dev Module**; enable **USB CDC On Boot** if needed.
4. Edit the constants at the top:
   ```cpp
   const char* WIFI_SSID = "YOUR_WIFI";
   const char* WIFI_PASS = "YOUR_PASS";
   const char* WS_URL     = "wss://<your-app>.onrender.com/ws";
   ```
5. Flash. The onboard LED lights while audio plays back. Mic gain is
   `MIC_GAIN_SHIFT` (higher = quieter).

## 💻 Run the backend locally

```bash
cd backend
python -m venv .venv
# Windows:        .\.venv\Scripts\activate
# Linux / macOS:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit values
```

Set at least `OLLAMA_API_KEY` in `.env` (from https://ollama.com/settings/keys),
then start the server:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Wait for `models ready`. On first run, Whisper and the Piper voice download
automatically.

## 🧪 Test without an ESP32

A PC-mic client streams your laptop mic to the server exactly like the ESP32 will
(needs `pip install sounddevice`). In a second terminal:

```bash
cd backend
python test_client.py           # or: python test_client.py ws://HOST:8000/ws
```

Say the wake word, then a question:

```
you: what is the capital of france
assistant: Paris is the capital of France.
```

## 🚀 Deploy to Render

1. Push this repo to GitHub.
2. On Render: **New → Blueprint**, point it at the repo. `render.yaml` provisions
   a Python web service from `backend/`.
3. Set the secret in the dashboard: `OLLAMA_API_KEY = your_key_here`.
4. Deploy, then point the firmware `WS_URL` at `wss://<your-app>.onrender.com/ws`.

Whisper and the Piper voice download on first startup — nothing to commit. The
blueprint defaults to `WHISPER_MODEL=tiny.en` for RAM-limited instances; bump to
`base.en` on a larger plan for better accuracy.

## ⚙️ Configuration

All settings live in `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_API_KEY` | — | **Required.** Ollama Cloud key |
| `OLLAMA_BASE_URL` | `https://ollama.com/v1` | OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | `gpt-oss:20b-cloud` | Hosted model (note the `-cloud` suffix) |
| `WAKEWORD_MODELS` | `hey_jarvis` | Built-in name or path to a custom `.onnx` |
| `WAKEWORD_THRESHOLD` | `0.5` | Detection sensitivity (0–1) |
| `WHISPER_MODEL` | `base.en` | `tiny.en` for speed, `base.en` for accuracy |
| `WHISPER_COMPUTE` | `int8` | CPU quantization |
| `SILENCE_RMS` | `500` | Below this = silence (end-of-speech) |
| `END_SILENCE_MS` | `800` | Silence needed to end a command |
| `MAX_COMMAND_MS` | `12000` | Hard cap on command length |
| `MIN_SPEECH_MS` | `300` | Minimum speech before a silence can end it |
| `PIPER_MODEL` / `PIPER_CONFIG` | `voices/en_US-lessac-medium…` | Voice files (auto-downloaded) |
| `SYSTEM_PROMPT` | short-answer prompt | Persona / style — answers are kept short because they are **spoken aloud** |

> To use a custom wake word, train one with the openWakeWord notebook, drop the
> `.onnx` into `backend/`, and set `WAKEWORD_MODELS=my_word.onnx`.

## 🔗 WebSocket protocol

**Client → Server**
- binary message = raw PCM mic audio (16 kHz / 16-bit / mono)

**Server → Client**
- `{"type":"transcript","text":...}` — what you said
- `{"type":"reply","text":...}` — the answer text
- `{"type":"play_start"}` → binary PCM chunks → `{"type":"play_end"}` — spoken audio

The firmware mutes the mic between `play_start` and `play_end` to prevent the
speaker feeding back into the mic. The connection is persistent and auto-reconnects.

## 🎚️ Tuning

| Symptom | Fix |
|---------|-----|
| Cuts you off / waits too long | adjust `SILENCE_RMS`, `END_SILENCE_MS` |
| Wake word too eager / too deaf | adjust `WAKEWORD_THRESHOLD` |
| Mic too loud / quiet | change `MIC_GAIN_SHIFT` in firmware |
| Slow transcription | use `WHISPER_MODEL=tiny.en` |

## 🩹 Troubleshooting & notes

- **Windows local audio:** `piper-tts` has no Windows wheel, so it can't be
  pip-installed on Windows. The server detects this and runs in **transcript-only
  mode** locally (you see text, no spoken audio). Full spoken audio works on Render
  (Linux) or any Linux/macOS host — `render.yaml` pins Python 3.11 where Piper
  installs cleanly.
- **No GPU needed:** Whisper runs on CPU with int8 quantization.
- **RAM:** Whisper + onnxruntime + Piper are tight on 512 MB instances — prefer
  `tiny.en` and a paid Render plan if the process gets OOM-killed.

---

<p align="center"><sub>Wake word · faster-whisper · Ollama Cloud · Piper · FastAPI · ESP32-S3</sub></p>
