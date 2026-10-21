FROM debian:trixie
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential bc bison flex libssl-dev libelf-dev dwarves cpio kmod python3 rsync xz-utils zstd \
    curl ca-certificates patch git file device-tree-compiler busybox-static gzip && rm -rf /var/lib/apt/lists/*
