FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (for potential cryptography/sqlite needs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for persistence
RUN mkdir -p /data

# Expose dashboard port
EXPOSE 5000

# Run the application
CMD ["python", "main.py"]
