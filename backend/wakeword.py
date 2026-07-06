from openwakeword.model import Model
import openwakeword.utils


class WakeWord:
    def __init__(self, models, threshold):
        try:
            openwakeword.utils.download_models()
        except Exception:
            pass
        model_list = [m.strip() for m in models.split(",") if m.strip()]
        self.model = Model(wakeword_models=model_list, inference_framework="onnx")
        self.threshold = threshold

    def detect(self, frame):
        scores = self.model.predict(frame)
        return any(score >= self.threshold for score in scores.values())

    def reset(self):
        self.model.reset()
