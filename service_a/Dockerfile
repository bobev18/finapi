FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if any are needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY service_a/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY service_a/ /app/service_a/

# Set Python path to find the packages
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "service_a.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
