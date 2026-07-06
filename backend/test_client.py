import asyncio
import json
import sys

import numpy as np
import sounddevice as sd
import websockets

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8000/ws"
SAMPLE_RATE = 16000
FRAME = 1280


async def main():
    state = {"playing": False, "buf": []}
    q = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def callback(indata, frames, time, status):
        loop.call_soon_threadsafe(q.put_nowait, bytes(indata))

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME, callback=callback
    )
    stream.start()
    print(f"connected mic, talking to {URL}")
    print("say your wake word, then a question...")

    async with websockets.connect(URL, max_size=None) as ws:

        async def sender():
            while True:
                data = await q.get()
                if not state["playing"]:
                    await ws.send(data)

        task = asyncio.create_task(sender())
        try:
            async for msg in ws:
                if isinstance(msg, bytes):
                    if state["playing"]:
                        state["buf"].append(np.frombuffer(msg, dtype=np.int16))
                    continue
                event = json.loads(msg)
                kind = event.get("type")
                if kind == "transcript":
                    print("you:", event["text"])
                elif kind == "play_start":
                    state["playing"] = True
                    state["buf"] = []
                    print("assistant speaking...")
                elif kind == "play_end":
                    audio = (
                        np.concatenate(state["buf"])
                        if state["buf"]
                        else np.zeros(0, dtype=np.int16)
                    )
                    state["playing"] = False
                    if audio.size:
                        sd.play(audio, SAMPLE_RATE)
                        sd.wait()
                    print("listening...")
        finally:
            task.cancel()
            stream.stop()
            stream.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
