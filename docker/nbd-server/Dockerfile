FROM debian:trixie
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nbd-server nbd-client util-linux e2fsprogs fdisk dosfstools rsync file >/dev/null && rm -rf /var/lib/apt/lists/*
