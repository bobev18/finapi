FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for yfinance or other C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY service_b/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared schemas package and service code
COPY shared/ /app/shared/
COPY service_b/ /app/service_b/

# Set Python path to find the packages
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8001

# Run FastAPI app
CMD ["uvicorn", "service_b.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
