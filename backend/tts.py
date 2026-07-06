import numpy as np


def _resample(samples, src_rate, dst_rate):
    if src_rate == dst_rate or samples.size == 0:
        return samples.astype(np.int16)
    dst_n = int(round(samples.size * dst_rate / src_rate))
    src_idx = np.arange(samples.size)
    dst_idx = np.linspace(0, samples.size - 1, dst_n)
    return np.interp(dst_idx, src_idx, samples).astype(np.int16)


class TTS:
    def __init__(self, model_path, config_path, out_rate):
        from piper import PiperVoice

        self.voice = PiperVoice.load(model_path, config_path)
        self.out_rate = out_rate

    def synthesize(self, text):
        rate = int(getattr(self.voice.config, "sample_rate", 22050))
        chunks = []
        for audio_bytes in self.voice.synthesize_stream_raw(text):
            chunks.append(np.frombuffer(audio_bytes, dtype=np.int16))
        samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
        return _resample(samples, rate, self.out_rate)
