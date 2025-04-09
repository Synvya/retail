# Base image (slim for smaller size)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if required, e.g., for psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Set environment variables
ENV PAYMENT_PROVIDER=square

# Expose port
EXPOSE 8000

# Start FastAPI using uvicorn with correct module path
CMD ["uvicorn", "src.retail_backend.core.main:app", "--host", "0.0.0.0", "--port", "8000"]