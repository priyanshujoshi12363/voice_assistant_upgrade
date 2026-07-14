<h1 align="center">🎙️ ESP32 Voice Q&A Assistant</h1>

<p align="center">
  <b>You talk to a tiny ESP32 gadget, it thinks in the cloud, and answers out loud.</b><br>
  The device is a dumb audio bridge with a cute OLED face; all the intelligence runs on a FastAPI server.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue.svg" alt="Python 3.11">
  <img src="https://img.shields.io/badge/FastAPI-WebSocket-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/ESP32-Arduino-red.svg" alt="ESP32">
  <img src="https://img.shields.io/badge/display-SSD1306%20OLED-white.svg" alt="OLED">
  <img src="https://img.shields.io/badge/LLM-Ollama%20Cloud-black.svg" alt="Ollama Cloud">
  <img src="https://img.shields.io/badge/deploy-Render-46E3B7.svg" alt="Render">
</p>

---

## 📖 What is this?

A standalone voice assistant split into two halves:

- **The device (ESP32 + mic + speaker + OLED):** captures your voice, streams it to
  the server over WiFi, plays back the spoken answer, and shows an animated face
  reflecting what it's doing.
- **The server (FastAPI, deployable to Render):** does the *thinking* — wake-word
  detection, speech-to-text, the LLM, and text-to-speech.

The device carries **no AI** and stores no secrets — it just moves audio. That
keeps the firmware tiny and lets you upgrade the "brain" any time by redeploying
the server.

## 🔁 The pipeline

Every stage and the exact audio/data format handed to the next:

```
 ┌──────────┐   16 kHz PCM     ┌──────────────────────────── SERVER (FastAPI) ────────────────────────────┐
 │  ESP32   │  ───binary────▶  │  1. Wake word     openWakeWord   detects "hey jarvis" in the live stream  │
 │  INMP441 │   over WiFi      │  2. Capture       energy VAD      records until you stop talking           │
 │   mic    │   WebSocket      │  3. STT           faster-whisper  audio ➜ text  (CPU, int8)                │
 └──────────┘                  │  4. LLM           Ollama Cloud    text ➜ answer (gpt-oss, tool-free chat)  │
 ┌──────────┐                  │  5. TTS           Piper           answer ➜ 16 kHz PCM                       │
 │  ESP32   │  ◀──binary────   │  6. Stream back   WebSocket       play_start ▸ audio chunks ▸ play_end     │
 │  DAC ➜   │   over WiFi      └───────────────────────────────────────────────────────────────────────────┘
 │ PAM8403  │   WebSocket
 │ speaker  │
 └──────────┘
```

**Step by step:**

1. **Stream** — The ESP32 reads its I2S mic continuously and sends raw
   **16 kHz / 16-bit / mono PCM** as binary WebSocket frames.
2. **Wake word** — The server runs [openWakeWord](https://github.com/dscripka/openWakeWord)
   on the stream (ONNX, CPU). Nothing else happens until the wake word fires.
3. **Capture** — After the wake word, a simple energy/RMS voice-activity detector
   records until ~0.8 s of silence (or a max duration).
4. **STT** — [faster-whisper](https://github.com/SYSTRAN/faster-whisper) transcribes
   the clip on the CPU with `int8` quantization (no GPU needed).
5. **LLM** — The transcript goes to **Ollama Cloud** (`gpt-oss`) through its
   OpenAI-compatible API; a short rolling history is kept for context.
6. **TTS** — [Piper](https://github.com/rhasspy/piper) synthesizes the reply to
   PCM, resampled to 16 kHz.
7. **Playback** — The server sends `play_start`, the PCM in chunks, then
   `play_end`. The ESP32 pushes the audio to its **internal DAC → PAM8403 →
   speaker**, and mutes its mic during playback to avoid feedback.

Throughout, the server also sends the recognized text and the answer text so the
**OLED** can display them.

## 🧰 Tech stack — what's used and why

| Layer | Tool | Why |
|-------|------|-----|
| Device MCU | **ESP32 (WROOM)** | Cheap, WiFi built-in, has an internal DAC for analog audio out |
| Mic | **INMP441** (I2S) | Clean digital 24-bit MEMS mic, no ADC noise |
| Amp/Speaker | **PAM8403** + speaker | Tiny class-D amp driven by the ESP32 DAC (GPIO25) |
| Display | **SSD1306 OLED** (I2C) | Shows status + an animated face |
| Firmware libs | **ArduinoWebsockets, Adafruit SSD1306/GFX, driver/i2s** | WebSocket client, OLED graphics, I2S mic + DAC |
| Transport | **WebSocket** (binary audio) | Persistent, low-latency, works through Render's HTTPS |
| Server | **FastAPI + Uvicorn** | Async ASGI, native WebSocket + a health route |
| Wake word | **openWakeWord** (ONNX) | Offline, lightweight, supports custom words |
| STT | **faster-whisper** (CTranslate2) | Fast CPU inference with int8; auto-downloads models |
| LLM | **Ollama Cloud – gpt-oss** | Hosted model via OpenAI-compatible API (`openai` SDK) |
| TTS | **Piper** | High-quality offline neural voices; auto-downloads |
| Audio math | **NumPy** | PCM buffering, RMS/VAD, resampling |
| Config | **python-dotenv** | All settings from `.env` |
| Deploy | **Render** (Blueprint / web service) | One-click Python service, WebSocket support |

## 📂 Repository structure

```
.
├── README.md
├── firmware/
│   └── voice_bridge.ino        ESP32: WiFi + WebSocket + I2S mic + DAC out + OLED face
└── backend/
    ├── server.py               FastAPI app — health route + /ws pipeline (the orchestrator)
    ├── config.py               Loads all settings from .env
    ├── wakeword.py             openWakeWord wrapper (detect / reset)
    ├── stt.py                  faster-whisper wrapper (CPU/int8, CUDA auto-detect)
    ├── llm.py                  Ollama Cloud chat client + rolling history
    ├── tts.py                  Piper synth + auto voice download + 16 kHz resample
    ├── test_client.py          PC-mic client to test the server without the ESP32
    ├── requirements.txt        Python dependencies
    ├── render.yaml             Render Blueprint (build/start/env)
    ├── Procfile                Start command (uvicorn)
    ├── .env.example            Copy to .env and fill in
    └── voices/                 Piper voice files land here (auto-downloaded)
```

### What each backend module does

- **`server.py`** — Accepts the WebSocket, holds one `Session` per device
  (its own wake-word model + LLM history), runs the feed→STT→LLM→TTS pipeline in a
  thread pool so the event loop never blocks, and streams audio + text back. A
  `GET /` health route keeps Render happy. Every command is wrapped in try/except
  so one failure never drops the connection.
- **`config.py`** — Typed settings pulled from `.env` (audio rates, wake word, VAD
  thresholds, Whisper model, Ollama credentials, Piper voice, system prompt).
- **`wakeword.py`** — Loads openWakeWord (ONNX) and reports when the score crosses
  the threshold.
- **`stt.py`** — Loads faster-whisper once; auto-uses CUDA if present else CPU/int8;
  converts int16 → float32 and transcribes with VAD filtering.
- **`llm.py`** — Thin OpenAI-compatible client pointed at Ollama Cloud; trims the
  message history so requests stay small.
- **`tts.py`** — Lazily loads Piper (so the app still boots where Piper isn't
  installed), auto-downloads the voice from `rhasspy/piper-voices` if missing, and
  resamples the output to 16 kHz for the device DAC.

## 🔌 Hardware & wiring

**Board:** ESP32 (WROOM / DevKit v1) — the *classic* ESP32, because audio out uses
the **internal 8-bit DAC** on GPIO25 (the ESP32-S3 has no DAC).

**🎤 INMP441 mic (I2S)**
| INMP441 | ESP32 |
|---------|-------|
| VCC | 3.3V |
| GND | GND |
| SCK | GPIO14 |
| WS  | GPIO15 |
| SD  | GPIO32 |
| L/R | GND |

**🖥️ SSD1306 OLED (I2C)**
| OLED | ESP32 |
|------|-------|
| VCC | 3.3V |
| GND | GND |
| SCL | GPIO22 |
| SDA | GPIO21 |

**🔈 PAM8403 amp + speaker**
| PAM8403 | ESP32 / Speaker |
|---------|-----------------|
| L (input) | GPIO25 (DAC) |
| 5V+ | 5V |
| 5V− | GND |
| − | GND |
| L+ / L− | Speaker + / − |

> 💡 Add a 470µF cap across PAM8403 power if the board resets on loud playback.

## 🛠️ Firmware

**Libraries (Arduino Library Manager):** `ArduinoWebsockets` (Gil Maimon),
`Adafruit SSD1306`, `Adafruit GFX`.

> ⚠️ **Use ESP32 Arduino core 2.0.x** (e.g. 2.0.17). Core 3.x removed the legacy
> I2S built-in-DAC API (`i2s_set_dac_mode`) this firmware uses for GPIO25 audio.

1. Open `firmware/voice_bridge.ino` in the Arduino IDE.
2. Install the esp32 board package (**2.0.x**) and the three libraries above.
3. Board: **ESP32 Dev Module** (or DOIT ESP32 DevKit v1).
4. Edit the constants at the top:
   ```cpp
   const char* WIFI_SSID = "YOUR_WIFI";
   const char* WIFI_PASS = "YOUR_PASS";
   const char* WS_URL     = "wss://<your-app>.onrender.com/ws";
   ```
5. Flash. Mic gain is `MIC_GAIN_SHIFT` (higher = quieter); if audio is quiet or
   distorted, also tune the PAM8403 pot.

### 🙂 The OLED face

A rounded-rectangle border with two rectangular eyes (+ pupils) and a mouth. The
expression follows the state, and the bottom strip scrolls what you said / the
answer:

| State | Face | Bottom text |
|-------|------|-------------|
| Connecting | sleepy eyes | `connecting` / `wifi...` / `server...` |
| Listening | happy (smile) | `listening` |
| Thinking | eyes look up, pupils dart, `. . .` mouth | your transcript |
| Speaking | mouth opens/closes with audio | the answer |

The face blinks every ~3 s. State is inferred from the server's `transcript`,
`reply`, `play_start`, and `play_end` messages.

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

Wait for `models ready`. Whisper and the Piper voice download automatically on
first run.

## 🧪 Test without the ESP32

A PC-mic client streams your laptop microphone to the server exactly like the
device will (needs `pip install sounddevice`). In a second terminal:

```bash
cd backend
python test_client.py           # or: python test_client.py ws://HOST:8000/ws
```

Say the wake word, then a question:

```
you: what is the capital of france
assistant: Paris is the capital of France.
```

> **Windows note:** `piper-tts` has no Windows wheel, so locally the server runs in
> **transcript-only mode** (you see text, no spoken audio). Full audio works on
> Render/Linux/macOS.

## 🚀 Deploy to Render

The simplest path is a **Web Service**:

- **Root directory:** `backend`
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
- **Environment:** set `OLLAMA_API_KEY` (secret). Optionally `WHISPER_MODEL=tiny.en`
  and `OLLAMA_MODEL=gpt-oss:20b-cloud`.
- **Python version:** 3.11 (Piper installs cleanly here).

`backend/render.yaml` captures the same settings if you prefer a Blueprint. After
deploy, point the firmware `WS_URL` at `wss://<your-app>.onrender.com/ws`.

> Whisper + the Piper voice download on first startup — nothing to commit.

## ⚙️ Configuration (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_API_KEY` | — | **Required.** Ollama Cloud key |
| `OLLAMA_BASE_URL` | `https://ollama.com/v1` | OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | `gpt-oss:20b-cloud` | Hosted model (note the `-cloud` suffix) |
| `WAKEWORD_MODELS` | `hey_jarvis` | Built-in name(s) or path to a custom `.onnx` |
| `WAKEWORD_THRESHOLD` | `0.5` | Detection sensitivity (0–1) |
| `WHISPER_MODEL` | `base.en` | `tiny.en` = faster, `base.en` = more accurate |
| `WHISPER_COMPUTE` | `int8` | CPU quantization |
| `SILENCE_RMS` | `500` | Below this = silence (end of speech) |
| `END_SILENCE_MS` | `800` | Silence needed to end a command |
| `MAX_COMMAND_MS` | `12000` | Hard cap on command length |
| `MIN_SPEECH_MS` | `300` | Minimum speech before a silence can end it |
| `PIPER_MODEL` / `PIPER_CONFIG` | `voices/en_US-lessac-medium…` | Voice files (auto-downloaded) |
| `SYSTEM_PROMPT` | short-answer prompt | Persona/style — kept short because replies are **spoken aloud** |

To use a **custom wake word**, train one with the openWakeWord notebook, put the
`.onnx` in `backend/`, and set `WAKEWORD_MODELS=my_word.onnx`.

## 🔗 WebSocket protocol (`/ws`)

**Client → Server**
- binary message = raw PCM mic audio (16 kHz / 16-bit / mono)

**Server → Client**
- `{"type":"transcript","text":...}` — what you said
- `{"type":"reply","text":...}` — the answer text
- `{"type":"play_start"}` → binary PCM chunks → `{"type":"play_end"}` — spoken audio

The connection is persistent; the firmware reconnects automatically if it drops,
and mutes the mic between `play_start`/`play_end` to prevent feedback.

## 🎚️ Tuning

| Symptom | Fix |
|---------|-----|
| Cuts you off / waits too long | adjust `SILENCE_RMS`, `END_SILENCE_MS` |
| Wake word too eager / too deaf | adjust `WAKEWORD_THRESHOLD` |
| Mic too loud / quiet | change `MIC_GAIN_SHIFT` in firmware / PAM8403 pot |
| Slow transcription | use `WHISPER_MODEL=tiny.en` |
| No sound on GPIO25 | flip DAC channel to `I2S_DAC_CHANNEL_RIGHT_EN` in firmware |

## 🩹 Notes & limitations

- **Windows local audio:** `piper-tts` has no Windows wheel → local server is
  transcript-only. Audio works on Render/Linux/macOS.
- **ESP32 core version:** the DAC path needs core **2.0.x** (3.x removed the API).
- **No GPU needed:** Whisper runs on CPU with int8.
- **RAM:** Whisper + onnxruntime + Piper are tight on 512 MB instances — prefer
  `tiny.en` and a paid Render plan if the process gets OOM-killed.

---

<p align="center"><sub>openWakeWord · faster-whisper · Ollama Cloud (gpt-oss) · Piper · FastAPI · NumPy · ESP32 · INMP441 · SSD1306 · PAM8403</sub></p>
