FROM python:3.10-slim

# Install system dependencies for TensorFlow/StarDist
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create models directory (will be overridden by volume mount)
RUN mkdir -p /models

EXPOSE 5000

# Use gunicorn for production-ready serving
# Timeout set high because model loading + prediction can take time
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "--workers", "2", "app:app"]
