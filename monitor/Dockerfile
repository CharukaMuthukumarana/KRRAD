# monitor/Dockerfile
# Use a modern Ubuntu image (supports Apple Silicon/ARM64)
FROM ubuntu:22.04

# Set non-interactive mode to prevent "Enter Geographic Area" prompts
ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory
WORKDIR /app

# 1. Install System Dependencies
# - bpfcc-tools: The core eBPF compiler
# - python3-pip: To install python libraries
# - python3-bpfcc: The Python bindings for eBPF
RUN apt-get update && \
    apt-get install -y bpfcc-tools python3-pip python3-bpfcc kmod linux-headers-generic && \
    rm -rf /var/lib/apt/lists/*

# 2. Install Python Dependencies
# We use the --break-system-packages flag because Ubuntu 24.04+ manages python strictly, 
# but for 22.04 this is just future-proofing or in case you use a newer base.
RUN pip3 install kubernetes flask

# 3. Copy our source code
COPY src/ /app/src/

# 4. Critical: Ensure Python can find the BCC libraries
ENV PYTHONPATH="/usr/lib/python3/dist-packages"

# 5. Run the loader
CMD ["python3", "src/loader.py"]