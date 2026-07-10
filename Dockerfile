# Use a lightweight official Python image
FROM python:3.11-slim

# Set environment paths and configurations
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copy configuration and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the core script
COPY main.py .

# Expose network port
EXPOSE 8000

# Execute the application
CMD ["python", "main.py"]
