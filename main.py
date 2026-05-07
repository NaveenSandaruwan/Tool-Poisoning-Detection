from app.api import create_app
from app.detector import get_detector


app = create_app()


def detect_poison(description: str) -> dict:
    """Detect if a description contains tool poisoning."""
    return get_detector().predict_one(description)


def batch_detect(descriptions: list[str]) -> list[dict]:
    """Detect tool poisoning across multiple descriptions."""
    return get_detector().predict_batch(descriptions)