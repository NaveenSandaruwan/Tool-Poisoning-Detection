from functools import lru_cache
import logging

from setfit import SetFitModel

from app.config import Settings, get_settings
from app.runtime import configure_runtime


LOGGER = logging.getLogger(__name__)
LABEL_MAP = {0: "Safe", 1: "Tool Poisoning"}


class ToolPoisoningDetector:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = SetFitModel.from_pretrained(settings.model_source)
        self._compile_model()

    def _compile_model(self) -> None:
        if not self.settings.use_torch_compile:
            return

        try:
            import torch

            if hasattr(torch, "compile"):
                self.model.model_body = torch.compile(self.model.model_body)
        except Exception:  # pragma: no cover - compilation is optional
            LOGGER.warning("torch.compile failed; continuing without compilation.")

    @staticmethod
    def _format_result(description: str, predicted_class: int, confidence: float) -> dict:
        return {
            "description": description,
            "predicted_class": predicted_class,
            "label": LABEL_MAP[predicted_class],
            "confidence": confidence,
            "is_poisoned": predicted_class == 1,
        }

    def predict_one(self, description: str) -> dict:
        pred = self.model.predict([description])
        probs = self.model.predict_proba([description])

        predicted_class = int(pred[0])
        confidence = float(probs[0][predicted_class])
        return self._format_result(description, predicted_class, confidence)

    def predict_batch(self, descriptions: list[str]) -> list[dict]:
        preds = self.model.predict(descriptions)
        probs = self.model.predict_proba(descriptions)

        results = []
        for index, description in enumerate(descriptions):
            predicted_class = int(preds[index])
            confidence = float(probs[index][predicted_class])
            results.append(self._format_result(description, predicted_class, confidence))
        return results


@lru_cache(maxsize=1)
def get_detector() -> ToolPoisoningDetector:
    settings = get_settings()
    configure_runtime(settings.thread_count)
    return ToolPoisoningDetector(settings)
