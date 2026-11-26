# AEGIS backend images. Build context: the repository root (see Dockerfile.dockerignore).
#   --target backend  web server, MQTT listener, push worker and database preparation
#   --target tools    migrations and backups: the same code next to the MySQL and MongoDB tools
# Neither image contains secrets, uploads or model weights.
FROM python:3.11-slim-bookworm AS backend

WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-serve.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-serve.txt

COPY backend/app ./app
COPY backend/database ./database
# register_models.py reads the model manifests; audit_iot_data.py checks stored IoT data.
COPY ai_service/api/checkpoint.json ai_service/api/gatekeeper.json /app/ai_service/api/
COPY tools/audit_iot_data.py /app/tools/

# Named volumes take their first ownership from these directories.
RUN useradd --system --uid 10001 --no-create-home aegis \
    && mkdir -p mysql-instance/uploads /app/run \
    && chown -R 10001 mysql-instance /app/run

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER 10001
EXPOSE 5000
# One worker so BACKEND_MAX_INFLIGHT matches what the AI service accepts; threads give
# the concurrency (requests mostly wait for MySQL or the AI service).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "16", "--timeout", "90", "app:create_app()"]


FROM mysql:8.4 AS tools
USER root
# mongodump and mongorestore come from MongoDB's own repository (same series as the server).
RUN rpm --import https://pgp.mongodb.com/server-7.0.asc \
    && printf '%s\n' '[mongodb-org-7.0]' 'name=MongoDB' \
       'baseurl=https://repo.mongodb.org/yum/redhat/9/mongodb-org/7.0/$basearch/' \
       'enabled=1' 'gpgcheck=1' 'gpgkey=https://pgp.mongodb.com/server-7.0.asc' \
       > /etc/yum.repos.d/mongodb-org-7.0.repo \
    && microdnf install -y python3.11 python3.11-pip mongodb-database-tools \
    && microdnf clean all
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt
COPY --from=backend /app /app
# COPY resets ownership. A fresh uploads volume mounted here first must stay writable
# for the backend (same uid).
RUN chown -R 10001 /app/backend/mysql-instance
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER 10001
ENTRYPOINT []
CMD ["python3.11", "database/migrate.py", "--status"]
