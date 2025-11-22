FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities (from parent project)
# NOTE: This Dockerfile assumes build context is set from project root
# When using docker-compose, the build context should be '.' (project root)
# Example: docker build -f g2-aol-template/Dockerfile -t my-agent .
# The paths below are relative to the project root where shared/ and aol-core/ exist
COPY shared/ /app/shared/
COPY aol-core/registry/ /app/registry/

# Copy service files
COPY . /app/service/

WORKDIR /app/service

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s \
    CMD python -c "import requests; requests.get('http://localhost:${HEALTH_PORT:-50200}/health').raise_for_status()"

CMD ["python", "agent.py"]
