# Use a lightweight Python image
FROM python:3.9-slim

# Forces Python to print logs immediately
ENV PYTHONUNBUFFERED=1 
# ---------------------

# Install system dependencies (including curl for kubectl)
RUN apt-get update && apt-get install -y \
    gcc \
    libpcap-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and models
COPY src/ src/
COPY models_dist/ models/

# Run the Controller
CMD ["python", "src/main.py"]