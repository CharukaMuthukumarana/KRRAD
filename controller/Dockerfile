# controller/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# 1. Install System Dependencies (standard PyPI)
# We remove the --index-url so pip looks in the normal place
RUN pip install --no-cache-dir \
    requests \
    joblib \
    pandas \
    numpy \
    kubernetes \
    torch \
    scikit-learn \
    prometheus_client

# 2. Copy Logic
COPY src/main.py /app/main.py

# 3. Copy Models
COPY models_dist/ /app/models/

CMD ["python", "-u", "main.py"]