# ESP32-S3 Voice Q&A Assistant (WebSocket / Render)

A standalone voice device: **you talk, it answers out loud.**

The **ESP32-S3** is a dumb audio bridge over **WiFi WebSocket**. It streams mic
audio to the server and plays back audio the server sends. All the smart stuff
runs on the server (deployable to **Render**):

```
ESP32 mic → WiFi WebSocket → [wake word] → [Whisper STT]
    → [Ollama Cloud gpt-oss] → [Piper TTS] → WebSocket → ESP32 speaker
```

No PC automation, no local audio — just voice questions and spoken answers.
Wake word runs on the server, so you can use **any custom word**.

---

## 1. Hardware & wiring

**Board:** ESP32-S3 SuperMini (PSRAM + two I2S peripherals)

**Mic — INMP441 (I2S input)**
| INMP441 | ESP32-S3 |
|---------|----------|
| VDD | 3.3V |
| GND | GND |
| SD  | GPIO4 |
| WS  | GPIO5 |
| SCK | GPIO6 |
| L/R | GND |

**Speaker — MAX98357A (I2S output)**
| MAX98357A | ESP32-S3 |
|-----------|----------|
| VIN | 5V |
| GND | GND |
| DIN | GPIO7 |
| BCLK | GPIO15 |
| LRC | GPIO16 |
| + / – | speaker terminals |

Add a 470µF cap across the MAX98357A VIN/GND if you get resets on loud playback.

---

## 2. Flash the firmware

1. Open `firmware/voice_bridge.ino` in Arduino IDE.
2. Install the **esp32** board package (Espressif).
3. Install the **ArduinoWebsockets** library (by Gil Maimon) from Library Manager.
4. Select board: **ESP32S3 Dev Module**, enable **USB CDC On Boot** if needed.
5. Edit the three constants at the top: `WIFI_SSID`, `WIFI_PASS`, `WS_URL`
   (`WS_URL` = `wss://<your-app>.onrender.com/ws`).
6. Flash. The onboard LED lights while audio is playing back.

---

## 3. Deploy the backend to Render

Push this repo to GitHub, then on Render: **New → Blueprint** and point it at the
repo. `render.yaml` provisions a Python web service from `backend/`.

Set the secret in the Render dashboard:
```
OLLAMA_API_KEY = your_key_here
```

The blueprint defaults to `WHISPER_MODEL=tiny.en` because the free/starter
instances are RAM-limited; bump to `base.en` on a larger instance for accuracy.

**Voices must be committed to the repo.** Download a Piper voice (`.onnx` +
`.onnx.json`) from the Piper voices release page and drop both into
`backend/voices/`. Point `PIPER_MODEL` / `PIPER_CONFIG` at them (defaults assume
`en_US-lessac-medium`).

### Ollama Cloud
1. Create an API key at **ollama.com/settings/keys**.
2. Model uses the hosted `-cloud` suffix, e.g. `gpt-oss:20b-cloud`.

---

## 4. Run locally (optional)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env         # then edit values
uvicorn server:app --host 0.0.0.0 --port 8000
```

Point the firmware `WS_URL` at `ws://<your-pc-ip>:8000/ws` for local testing
(plain `ws://`, and remove `client.setInsecure();` is not needed since it is a
no-op on non-TLS).

No GPU needed — Whisper runs on CPU with int8 quantization.

---

## WebSocket protocol

- **Client → Server:** binary messages = raw PCM mic audio (16 kHz / 16-bit / mono).
- **Server → Client:**
  - text `{"type":"transcript","text":...}` — what you said (debug).
  - text `{"type":"play_start"}` then binary PCM chunks then text `{"type":"play_end"}` — the spoken answer.

The firmware mutes the mic while `playing` (between `play_start`/`play_end`) to
avoid the speaker feeding back into the mic.

## Tuning
- `SILENCE_RMS`, `END_SILENCE_MS` control when the server decides you're done
  talking. Tune if it cuts you off or waits too long.
- Mic gain: change `MIC_GAIN_SHIFT` in the firmware (higher = quieter).
