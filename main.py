from fastapi import FastAPI
from pydantic import BaseModel
from setfit import SetFitModel

# Initialize FastAPI app
app = FastAPI(title="Poison Detection API")

# Load the model at startup
model = SetFitModel.from_pretrained("poison_detection_model")

# Label mapping
LABEL_MAP = {0: "Safe", 1: "Tool Poisoning"}


class DescriptionRequest(BaseModel):
    description: str


class PredictionResponse(BaseModel):
    description: str
    predicted_class: int
    label: str
    confidence: float
    is_poisoned: bool


def detect_poison(description: str) -> dict:
    """Detect if a description contains tool poisoning."""
    pred = model.predict([description])
    probs = model.predict_proba([description])
    
    predicted_class = int(pred[0])
    confidence = float(probs[0][predicted_class])
    label = LABEL_MAP[predicted_class]
    
    return {
        "description": description,
        "predicted_class": predicted_class,
        "label": label,
        "confidence": confidence,
        "is_poisoned": predicted_class == 1
    }


@app.post("/detect", response_model=PredictionResponse)
def detect_endpoint(request: DescriptionRequest):
    """Endpoint to detect if a description is poisoned."""
    return detect_poison(request.description)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}