# =============================================================================
# STAGE 1: builder
# Purpose: Compile the Fortran source into a Python extension (.so) using f2py.
# This stage uses gfortran and full build tooling — it is NEVER shipped.
# =============================================================================
FROM --platform=linux/amd64 python:3.11-slim AS builder

LABEL stage="builder"

# Install OS-level build dependencies AND locales
RUN apt-get update && apt-get install -y --no-install-recommends \
    gfortran \
    gcc \
    build-essential \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Configure UTF-8 encoding so f2py doesn't crash on special characters
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8  
ENV LANGUAGE=en_US:en  
ENV LC_ALL=en_US.UTF-8

# Install NumPy and build tools
RUN pip install --no-cache-dir numpy==1.26.4 setuptools==69.5.1 charset-normalizer

ENV SETUPTOOLS_USE_DISTUTILS=local

WORKDIR /build

# Copy Fortran source
COPY schrodinger.f90 .

# ── Compile Fortran → Python extension module via f2py ──────────────────────
# Flags:
#   -c           : compile and link
#   -m           : output module name
#   --f90flags   : enable full IEEE floating-point compliance
#   --opt        : O3 optimization
RUN python -m numpy.f2py \
      -c schrodinger.f90 \
      -m schrodinger_mod \
      --f90flags="-ffree-form -fdefault-real-8" \
      --opt="-O3"

# Verify the .so was produced (build will fail here if Fortran has errors)
RUN ls -lh schrodinger_mod*.so && echo "✅ Fortran module compiled successfully."

# =============================================================================
# STAGE 2: runtime
# Purpose: Lean production image. Only ships the compiled .so + Python scripts.
# =============================================================================
FROM --platform=linux/amd64 python:3.11-slim AS runtime

LABEL maintainer="quantum-compute-labs"
LABEL description="Schrödinger wave equation parallel worker"

# Install only runtime OS deps (no gcc, no gfortran)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgfortran5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python runtime dependencies
RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    redis==5.0.4 \
    fastapi==0.111.0 \
    uvicorn==0.29.0

WORKDIR /app

# Copy ONLY the compiled Fortran .so from the builder stage
COPY --from=builder /build/schrodinger_mod*.so ./

# Copy the Python worker script
COPY parallel_worker.py .

# Create the PV mount point directory
RUN mkdir -p /mnt/results

# Runtime environment defaults (overridden by Kubernetes env vars)
ENV REDIS_HOST="localhost"
ENV REDIS_PORT="6379"
ENV GRID_SIZE="100"
ENV TOTAL_JOBS="10"
ENV JOB_COMPLETION_INDEX="0"

# The worker is a one-shot job, not a long-running server
CMD ["python", "parallel_worker.py"]
