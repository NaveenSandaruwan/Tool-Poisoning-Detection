from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from setfit import SetFitModel
from optimum.bettertransformer import BetterTransformer
import torch

# Initialize FastAPI app
app = FastAPI(title="Poison Detection API")

# Allow all CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



# 1. Load the model
model = SetFitModel.from_pretrained("poison_detection_model")

# 2. Convert the internal sentence_transformer to a Faster version
# This works on most CPUs and doesn't require the 'to_onnx' method
model.model_body = BetterTransformer.transform(model.model_body)

# 3. Critical for CPU utilization:
torch.set_num_threads(2)

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

def batch_detect(descriptions: list[str]) -> list[dict]:
  
    # 1. Run the model ONCE on the entire list (Vectorized)
    preds = model.predict(descriptions)
    probs = model.predict_proba(descriptions)
    
    # 2. Format results
    results = []
    for i, desc in enumerate(descriptions):
        predicted_class = int(preds[i])
        results.append({
            "description": desc,
            "predicted_class": predicted_class,
            "label": LABEL_MAP[predicted_class],
            "confidence": float(probs[i][predicted_class]),
            "is_poisoned": predicted_class == 1
        })
    return results

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

@app.post("/batch_detect", response_model=list[PredictionResponse])
def batch_detect_endpoint(requests: list[DescriptionRequest]):
    """Endpoint to detect if multiple descriptions are poisoned."""
    descriptions = [req.description for req in requests]
    return batch_detect(descriptions)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}