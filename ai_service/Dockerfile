# CPU image of the AEGIS AI service. Build context: ai_service/. Model weights are NOT in the
# image: mount them at /app/experiments (the service checks their SHA-256 at startup).
FROM python:3.11-slim-bookworm

# opencv-python, required by ultralytics, loads these at import time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/api
COPY api/requirements.txt api/requirements-serve.txt ./
# CPU PyTorch first; otherwise ultralytics pulls the much larger CUDA build.
RUN pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt -r requirements-serve.txt
COPY api/app.py api/diagnosis.py api/checkpoint.json api/gatekeeper.json ./

RUN useradd --system --uid 10001 --no-create-home aegis

# At run time ultralytics must neither reach the network nor install packages, and it may only
# write to /tmp (the root filesystem can be read-only).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    YOLO_CONFIG_DIR=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    YOLO_OFFLINE=true \
    YOLO_AUTOINSTALL=false

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

# One worker: one copy of each model, and AEGIS_AI_MAX_INFLIGHT is counted per process. The extra
# threads keep /health and the 503 ai_busy answer available while predictions are running.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "120", "app:create_app()"]
