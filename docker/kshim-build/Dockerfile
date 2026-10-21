FROM debian:trixie
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    gcc g++ binutils cmake ninja-build python3 git make device-tree-compiler gzip ca-certificates file xxd && rm -rf /var/lib/apt/lists/*
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3-pip && pip3 install --break-system-packages kconfiglib && rm -rf /var/lib/apt/lists/*
ENV TERM=xterm-256color
