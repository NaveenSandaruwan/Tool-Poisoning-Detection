from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.detector import get_detector
from app.schemas import DescriptionRequest, PredictionResponse


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        get_detector()
        yield

    app = FastAPI(title="Poison Detection API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/detect", response_model=PredictionResponse)
    def detect_endpoint(request: DescriptionRequest):
        return get_detector().predict_one(request.description)

    @app.post("/batch_detect", response_model=list[PredictionResponse])
    def batch_detect_endpoint(requests: list[DescriptionRequest]):
        descriptions = [request.description for request in requests]
        return get_detector().predict_batch(descriptions)

    @app.get("/health")
    def health_check():
        return {"status": "healthy"}

    return app
