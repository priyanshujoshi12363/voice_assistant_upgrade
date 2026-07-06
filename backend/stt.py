import numpy as np
from faster_whisper import WhisperModel


def _device():
    try:
        from ctranslate2 import get_cuda_device_count

        if get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


class STT:
    def __init__(self, model, compute):
        device = _device()
        if device == "cpu" and compute in ("float16", "int8_float16"):
            compute = "int8"
        self.model = WhisperModel(model, device=device, compute_type=compute)

    def transcribe(self, audio):
        if audio is None or audio.size == 0:
            return ""
        data = audio.astype(np.float32) / 32768.0
        segments, _ = self.model.transcribe(
            data, language="en", beam_size=1, vad_filter=True
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
