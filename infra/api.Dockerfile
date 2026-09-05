FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv/backend
RUN groupadd --gid 10001 socra && useradd --uid 10001 --gid socra --create-home socra
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ ./
COPY contracts/ /srv/contracts/
RUN mkdir -p /data/files /data/deletions && chown -R socra:socra /data /srv/backend
USER socra
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
