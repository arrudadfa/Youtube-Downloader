FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY src/ src/

# Apenas defaults não sensíveis. Tokens, senhas e chaves de API
# devem ser configurados na plataforma de deploy (env vars em runtime).
ENV LOCAL_STORAGE_PATH=/app/downloads \
    INSTAGRAM_SESSION_PATH=/app/data/instagram_session.json \
    FFMPEG_PATH=ffmpeg \
    LOG_LEVEL=INFO \
    BOT_MODE=polling

RUN mkdir -p data downloads

VOLUME ["/app/data", "/app/downloads"]

CMD ["python", "main.py"]
