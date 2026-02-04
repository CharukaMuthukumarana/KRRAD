FROM ubuntu:24.04

# Install hping3 during the build
RUN apt-get update && apt-get install -y hping3 iputils-ping

# Keep the container alive forever so we can log in
CMD ["sleep", "infinity"]