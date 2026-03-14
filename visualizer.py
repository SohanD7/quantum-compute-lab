"""
visualizer.py
─────────────────────────────────────────────────────────────
Local Matplotlib client for Quantum Compute Labs.

Subscribes to the EC2 Redis 'wave_channel' and animates each
incoming JSON matrix payload as a live 3D surface plot.

Usage:
    python visualizer.py --host 34.212.0.152 --port 6379
"""

import argparse
import json
import threading
import queue
import time
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.animation import FuncAnimation
import redis

# ── Argument parsing ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Quantum Wave Visualizer")
parser.add_argument("--host", default="34.212.0.152", help="Redis EC2 public IP")
parser.add_argument("--port", type=int, default=6379, help="Redis port")
args = parser.parse_args()

REDIS_HOST  = args.host
REDIS_PORT  = args.port
CHANNEL     = "wave_channel"

# ── Thread-safe queue: Redis thread → Matplotlib thread ───────────────────────
frame_queue = queue.Queue(maxsize=50)

# ── Track metadata for title display ──────────────────────────────────────────
metadata = {
    "worker_index": 0,
    "num_steps":    0,
    "elapsed_s":    0.0,
    "frame_count":  0,
    "total_bytes":  0,
}

# ══════════════════════════════════════════════════════════════════════════════
# Redis subscriber thread
# Runs in background, pushes decoded matrices into frame_queue
# ══════════════════════════════════════════════════════════════════════════════
def redis_subscriber():
    print(f"[Redis] Connecting to {REDIS_HOST}:{REDIS_PORT}...")
    while True:
        try:
            client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            client.ping()
            print(f"[Redis] Connected. Subscribing to '{CHANNEL}'...")

            pubsub = client.pubsub()
            pubsub.subscribe(CHANNEL)

            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                    matrix  = np.array(payload["matrix"], dtype=np.float64)

                    # Update shared metadata
                    metadata["worker_index"] = payload.get("worker_index", 0)
                    metadata["num_steps"]    = payload.get("num_steps", 0)
                    metadata["elapsed_s"]    = payload.get("elapsed_s", 0.0)
                    metadata["frame_count"] += 1
                    metadata["total_bytes"] += len(message["data"])

                    # Non-blocking put — drop frame if queue full (backpressure)
                    try:
                        frame_queue.put_nowait(matrix)
                    except queue.Full:
                        pass

                    print(
                        f"[Redis] Frame {metadata['frame_count']:>4} received — "
                        f"worker={metadata['worker_index']} "
                        f"k={metadata['num_steps']} "
                        f"size={len(message['data'])//1024}KB"
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[Redis] Parse error: {e}")

        except redis.exceptions.ConnectionError as e:
            print(f"[Redis] Connection lost: {e}. Retrying in 3s...")
            time.sleep(3)

# ══════════════════════════════════════════════════════════════════════════════
# Matplotlib 3D surface animation
# ══════════════════════════════════════════════════════════════════════════════
def build_grid(n: int):
    x = np.linspace(0, 1, n)
    y = np.linspace(0, 1, n)
    return np.meshgrid(x, y)

# Initial flat surface while waiting for first frame
GRID_SIZE   = 100
X, Y        = build_grid(GRID_SIZE)
Z_INIT      = np.zeros((GRID_SIZE, GRID_SIZE))

fig = plt.figure(figsize=(13, 7), facecolor="#0d0d0d")
fig.suptitle(
    "Quantum Compute Labs — Live Schrödinger Wave Visualizer",
    color="white", fontsize=13, fontweight="bold", y=0.97
)

ax = fig.add_subplot(111, projection="3d", facecolor="#0d0d0d")

# Initial plot surface
surf = [ax.plot_surface(X, Y, Z_INIT, cmap=cm.plasma,
                         linewidth=0, antialiased=True, alpha=0.9)]

# Axes styling
ax.set_xlabel("X", color="white", labelpad=8)
ax.set_ylabel("Y", color="white", labelpad=8)
ax.set_zlabel("Ψ(x,y)", color="white", labelpad=8)
ax.tick_params(colors="white")
for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
    pane.fill = False
    pane.set_edgecolor("#333333")
ax.grid(True, color="#222222", linestyle="--", alpha=0.5)

# Status text box in bottom-left
status_text = fig.text(
    0.01, 0.02,
    "Waiting for wave data from Redis...",
    color="#00ff88", fontsize=9,
    fontfamily="monospace",
    bbox=dict(facecolor="#111111", edgecolor="#333333", boxstyle="round,pad=0.4")
)

# Colorbar
cbar = fig.colorbar(surf[0], ax=ax, shrink=0.4, pad=0.1)
cbar.ax.yaxis.set_tick_params(color="white")
plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
cbar.set_label("Wave Amplitude Ψ", color="white")

def animate(frame_num):
    """Called by FuncAnimation every 100ms. Pulls latest matrix from queue."""
    if frame_queue.empty():
        return

    matrix = frame_queue.get_nowait()
    n      = matrix.shape[0]

    # Rebuild grid if size changed
    global X, Y, GRID_SIZE
    if n != GRID_SIZE:
        GRID_SIZE = n
        X, Y      = build_grid(n)

    # Remove old surface and draw new one
    surf[0].remove()
    surf[0] = ax.plot_surface(
        X, Y, matrix,
        cmap=cm.plasma,
        linewidth=0,
        antialiased=True,
        alpha=0.9
    )

    # Auto-scale Z axis
    z_min, z_max = float(matrix.min()), float(matrix.max())
    ax.set_zlim(z_min - 0.05, z_max + 0.05)

    # Update colorbar scale
    surf[0].set_clim(z_min, z_max)

    # Update status text
    status_text.set_text(
        f"  Worker: {metadata['worker_index']:>2}  |  "
        f"Time-step k={metadata['num_steps']:>3}  |  "
        f"Compute: {metadata['elapsed_s']*1000:.2f}ms  |  "
        f"Frames received: {metadata['frame_count']:>4}  |  "
        f"Data: {metadata['total_bytes']//1024:>6} KB  "
    )

    # Slowly rotate the view for visual effect
    ax.view_init(elev=28, azim=(frame_num * 1.5) % 360)

ani = FuncAnimation(
    fig,
    animate,
    interval=100,      # poll queue every 100ms
    cache_frame_data=False,
)

plt.tight_layout(rect=[0, 0.05, 1, 0.95])

# ── Start Redis subscriber in background thread ────────────────────────────────
t = threading.Thread(target=redis_subscriber, daemon=True)
t.start()

print("[Visualizer] Starting Matplotlib window. Close it to exit.")
print(f"[Visualizer] Listening on Redis {REDIS_HOST}:{REDIS_PORT} → {CHANNEL}")
plt.show()
