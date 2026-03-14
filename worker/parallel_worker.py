"""
parallel_worker.py
------------------
Kubernetes Indexed Job worker for the Quantum Compute Labs pipeline.

Environment Variables (injected by Kubernetes):
    JOB_COMPLETION_INDEX : int  — The pod's index (0 to completions-1)
    REDIS_HOST           : str  — Hostname/IP of the EC2 Redis broker
    REDIS_PORT           : int  — Redis port (default: 6379)
    GRID_SIZE            : int  — NxN matrix dimension (default: 100)
    TOTAL_JOBS           : int  — Total number of parallel workers (default: 10)
"""

import os
import sys
import json
import time
import logging
import numpy as np
import redis

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Worker-%(worker_index)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# ── Read environment variables ─────────────────────────────────────────────────
WORKER_INDEX  = int(os.environ.get("JOB_COMPLETION_INDEX", 0))
REDIS_HOST    = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT    = int(os.environ.get("REDIS_PORT", 6379))
GRID_SIZE     = int(os.environ.get("GRID_SIZE", 100))
TOTAL_JOBS    = int(os.environ.get("TOTAL_JOBS", 10))
RESULTS_DIR   = "/mnt/results"

logger = logging.LoggerAdapter(logging.getLogger(__name__), {"worker_index": WORKER_INDEX})

# ── Import the f2py-compiled Fortran module ────────────────────────────────────
try:
    import schrodinger_mod as fortran_engine
    logger.info("Fortran module 'schrodinger_mod' loaded successfully.")
except ImportError as e:
    logger.error(f"FATAL: Could not import Fortran module: {e}")
    sys.exit(1)

# ── Physics parameters ─────────────────────────────────────────────────────────
H_BAR      = 1.0545718e-34   # Reduced Planck constant (J·s)
MASS       = 9.10938e-31     # Electron mass (kg)
NUM_STEPS  = WORKER_INDEX + 1  # Each worker computes a distinct time-step slice

def connect_redis(retries: int = 5, delay: float = 3.0) -> redis.Redis:
    """Connect to Redis with retry logic for pod startup race conditions."""
    for attempt in range(1, retries + 1):
        try:
            client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            client.ping()
            logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return client
        except redis.exceptions.ConnectionError as e:
            logger.warning(f"Redis connection attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay)
    logger.error("FATAL: Could not connect to Redis after all retries.")
    sys.exit(1)

def compute_wave_chunk() -> np.ndarray:
    """
    Allocate an NxN matrix and call the Fortran subroutine to populate it.
    Returns the computed 2D wave amplitude array.
    """
    logger.info(f"Allocating {GRID_SIZE}x{GRID_SIZE} matrix for time-step k={NUM_STEPS}...")
    # Fortran expects Fortran-contiguous (column-major) float64 array
    matrix = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float64, order='F')

    start = time.perf_counter()
    fortran_engine.schrodinger_mod.compute_wave_matrix(
        size_n    = GRID_SIZE,
        matrix    = matrix,
        num_steps = NUM_STEPS,
        h_bar     = H_BAR,
        mass      = MASS,
    )
    elapsed = time.perf_counter() - start
    logger.info(f"Fortran computation complete in {elapsed:.4f}s.")
    return matrix, elapsed

def publish_chunk(client: redis.Redis, matrix: np.ndarray, elapsed: float):
    """
    Serialize the wave matrix chunk to JSON and publish to Redis wave_channel.
    Payload schema:
        {
          "worker_index": int,
          "num_steps":    int,
          "grid_size":    int,
          "elapsed_s":    float,
          "matrix":       List[List[float]]   # GRID_SIZE x GRID_SIZE
        }
    """
    payload = {
        "worker_index": WORKER_INDEX,
        "num_steps":    NUM_STEPS,
        "grid_size":    GRID_SIZE,
        "elapsed_s":    round(elapsed, 6),
        "matrix":       matrix.tolist(),
    }
    message = json.dumps(payload)
    receivers = client.publish("wave_channel", message)
    logger.info(
        f"Published chunk to 'wave_channel' "
        f"({len(message)} bytes, {receivers} active subscriber(s))."
    )
    return payload

def write_result_log(payload: dict):
    """Write a summary log to the Persistent Volume mount."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    log_path = os.path.join(RESULTS_DIR, f"worker_{WORKER_INDEX:03d}_result.json")
    summary = {
        "worker_index": payload["worker_index"],
        "num_steps":    payload["num_steps"],
        "grid_size":    payload["grid_size"],
        "elapsed_s":    payload["elapsed_s"],
        "matrix_min":   float(np.min(payload["matrix"])),
        "matrix_max":   float(np.max(payload["matrix"])),
        "timestamp":    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(log_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Result summary written to PV at {log_path}")

# ── Main execution ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info(f"Quantum Compute Labs — Worker Pod Starting")
    logger.info(f"  Worker Index : {WORKER_INDEX} / {TOTAL_JOBS - 1}")
    logger.info(f"  Grid Size    : {GRID_SIZE}x{GRID_SIZE}")
    logger.info(f"  Redis Target : {REDIS_HOST}:{REDIS_PORT}")
    logger.info("=" * 60)

    # 1. Connect to Redis broker
    redis_client = connect_redis()

    # 2. Run Fortran computation
    matrix, elapsed = compute_wave_chunk()

    # 3. Publish result to Redis Pub/Sub channel
    payload = publish_chunk(redis_client, matrix, elapsed)

    # 4. Write summary log to Persistent Volume
    write_result_log(payload)

    logger.info("Worker completed successfully. Exiting.")
    sys.exit(0)
