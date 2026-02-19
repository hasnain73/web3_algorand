# ── Flask Frontend Dockerfile ──────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Expose Flask port
EXPOSE 5000

# Environment defaults (override via docker-compose or -e flags)
ENV FLASK_DEBUG=0
ENV PORT=5000

CMD ["python", "app.py"]