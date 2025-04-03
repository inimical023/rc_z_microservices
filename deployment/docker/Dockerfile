FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY setup.py /app/
COPY README.md /app/

# Create a temporary package to install dependencies
RUN mkdir -p /app/rc_zoho_microservices
RUN touch /app/rc_zoho_microservices/__init__.py

# Install dependencies
RUN pip install --no-cache-dir -e .

# Copy the rest of the application
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/templates /app/static

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command
CMD ["python", "-m", "rc_zoho_microservices.admin_service.service"]