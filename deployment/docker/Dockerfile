FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and setup files
COPY requirements.txt /app/
COPY setup.py /app/
COPY README.md /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/templates /app/static

# Set Python path
ENV PYTHONPATH=/app

# Expose ports (all services)
EXPOSE 8000 8001 8002 8003 8004

# Command will be overridden by docker-compose.yml
CMD ["python", "/app/admin_service/service.py"] 