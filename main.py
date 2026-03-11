import time
import logging
import psutil
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from setfit import SetFitModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Poison Detection API")

# Allow all CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the model at startup
model = SetFitModel.from_pretrained("poison_detection_model")

# Label mapping
LABEL_MAP = {0: "Safe", 1: "Tool Poisoning"}

# Process handle for per-request memory tracking
_process = psutil.Process(os.getpid())


def _parse_cpuset_cpus(s: str) -> int:
    parts = [p.strip() for p in s.split(',') if p.strip()]
    total = 0
    for part in parts:
        if '-' in part:
            a, b = part.split('-')
            total += int(b) - int(a) + 1
        else:
            total += 1
    return total


def get_cgroup_cpu_quota() -> float | None:
    """Return number of CPUs allowed by cgroup (v2 or v1) or None if not limited."""
    # cgroup v2: /sys/fs/cgroup/cpu.max -> "max" or "<quota> <period>"
    try:
        with open("/sys/fs/cgroup/cpu.max", "r") as f:
            data = f.read().strip().split()
            if data and data[0] != "max":
                quota = int(data[0])
                period = int(data[1]) if len(data) > 1 else 100000
                if quota > 0 and period > 0:
                    return quota / period
    except Exception:
        pass

    # cgroup v1
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "r") as f:
            quota = int(f.read().strip())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "r") as f:
            period = int(f.read().strip())
        if quota > 0 and period > 0:
            return quota / period
    except Exception:
        pass

    # cpuset (explicit CPU list)
    try:
        with open("/sys/fs/cgroup/cpuset/cpuset.cpus", "r") as f:
            s = f.read().strip()
            if s:
                return float(_parse_cpuset_cpus(s))
    except Exception:
        pass

    return None


def get_effective_cpu_count() -> float:
    """Best-effort number of CPUs available to this process (may be fractional)."""
    try:
        host = os.cpu_count() or 1
    except Exception:
        host = 1
    quota = get_cgroup_cpu_quota()
    if quota is None:
        return float(host)
    # quota may be fractional, return the smaller of host and quota
    return float(min(host, quota))


def log_performance(endpoint: str, elapsed_s: float, item_count: int = 1):
    cpu = psutil.cpu_percent(interval=None)
    mem = _process.memory_info().rss / 1024 / 1024  # MB
    allowed = get_effective_cpu_count()
    logger.info(
        "endpoint=%-14s | items=%3d | time=%6.3fs | cpu=%5.1f%% | mem=%7.1fMB | allowed_cpus=%.2f",
        endpoint, item_count, elapsed_s, cpu, mem, allowed,
    )


@app.middleware("http")
async def perf_middleware(request: Request, call_next):
    start_wall = time.perf_counter()
    start_cpu = _process.cpu_times().user + _process.cpu_times().system
    response = await call_next(request)
    end_cpu = _process.cpu_times().user + _process.cpu_times().system
    end_wall = time.perf_counter()
    cpu_seconds = end_cpu - start_cpu
    wall_seconds = end_wall - start_wall
    avg_cores = cpu_seconds / wall_seconds if wall_seconds > 0 else 0.0
    cpu = psutil.cpu_percent(interval=None)
    mem = _process.memory_info().rss / 1024 / 1024
    allowed = get_effective_cpu_count()
    logger.info(
        "REQUEST %-25s | status=%d | time=%6.3fs | cpu=%5.1f%% | cpu_sec=%.6fs | avg_cores=%.3f | allowed_cpus=%.2f | mem=%7.1fMB",
        request.url.path, response.status_code, wall_seconds, cpu, cpu_seconds, avg_cores, allowed, mem,
    )
    return response


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
    start = time.perf_counter()
    pred = model.predict([description])
    probs = model.predict_proba([description])
    elapsed = time.perf_counter() - start

    predicted_class = int(pred[0])
    confidence = float(probs[0][predicted_class])
    label = LABEL_MAP[predicted_class]

    logger.info("inference | time=%6.3fs | label=%-14s | confidence=%.4f", elapsed, label, confidence)

    return {
        "description": description,
        "predicted_class": predicted_class,
        "label": label,
        "confidence": confidence,
        "is_poisoned": predicted_class == 1,
    }


@app.post("/detect", response_model=PredictionResponse)
def detect_endpoint(request: DescriptionRequest):
    start = time.perf_counter()
    result = detect_poison(request.description)
    log_performance("/detect", time.perf_counter() - start, item_count=1)
    return result


@app.post("/batch_detect", response_model=list[PredictionResponse])
def batch_detect_endpoint(requests: list[DescriptionRequest]):
    start = time.perf_counter()
    results = [detect_poison(req.description) for req in requests]
    log_performance("/batch_detect", time.perf_counter() - start, item_count=len(requests))
    return results


@app.get("/health")
def health_check():
    cpu = psutil.cpu_percent(interval=None)
    mem = _process.memory_info().rss / 1024 / 1024
    return {"status": "healthy", "cpu_percent": cpu, "memory_mb": round(mem, 1)}