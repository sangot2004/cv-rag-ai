FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  curl \
  libgomp1 \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
  pip install --no-cache-dir -r requirements.txt

COPY main.py alembic.ini ./
COPY src ./src
COPY alembic ./alembic
COPY scripts ./scripts

RUN useradd --create-home --uid 10001 app && \
  mkdir -p /app/data /app/runtime /home/app/.cache && \
  chown -R app:app /app/data /app/runtime /home/app/.cache

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
