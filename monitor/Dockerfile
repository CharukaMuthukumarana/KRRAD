# monitor/Dockerfile
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# 1. Install Dependencies & Headers
RUN apt-get update && \
    apt-get install -y bpfcc-tools python3-pip python3-bpfcc kmod linux-headers-generic && \
    rm -rf /var/lib/apt/lists/*

# 2. Install Python Libs
RUN pip3 install --break-system-packages kubernetes flask

# 3. Copy Code
COPY src/ /app/src/

# 4. Setup Entrypoint (Make it executable)
RUN chmod +x /app/src/entrypoint.sh

# 5. Environment
ENV PYTHONPATH="/usr/lib/python3/dist-packages"

# 6. Start via the wrapper script
CMD ["/app/src/entrypoint.sh"]