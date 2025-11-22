FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Generate protobuf files
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=. \
    --grpc_python_out=. \
    ./proto/common.proto \
    ./proto/health.proto \
    ./proto/metrics.proto \
    ./proto/service.proto

# Expose ports (defaults - should be overridden in docker-compose)
EXPOSE 50050 50100 50200 8080

# Run the application
CMD ["python", "service/main.py"]
