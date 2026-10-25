# Use official Python 3.11 slim image.
# We choose 'slim' over 'alpine' because Python binary wheels (like uvicorn with C extensions)
# compile seamlessly on Debian glibc without requiring extra gcc/musl build tooling.
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Set Python environment flags:
# PYTHONDONTWRITEBYTECODE: prevents Python from writing .pyc files to disk
# PYTHONUNBUFFERED: ensures stdout and stderr are sent straight to terminal without buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


COPY requirements.txt .

# Install dependencies using --no-cache-dir to keep the Docker image lightweight
RUN pip install --no-cache-dir -r requirements.txt


COPY . .

# Expose port 8000 for FastAPI / Uvicorn traffic
EXPOSE 8000

# Start Uvicorn in production mode (bound to 0.0.0.0, no --reload)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
