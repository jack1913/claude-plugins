# The Linux validation image for brand-creator: everything the plugin documents for Linux, nothing else.
#
#   tests/docker/run.sh                 builds this image and runs the whole suite and the Acme smoke inside it
#
# Base: Debian 13 (trixie), pinned by version tag. Python comes from the distribution (3.13), Node is the official 24.x tarball
# (checked against the published SHA-256), uv is the official image copy. The plugin itself and its data directory (npm packages
# and Chromium, installed by `brand-creator setup`) are NOT part of the image: run.sh copies the plugin in at run time, so the
# image never goes stale and setup is tested as a user runs it.
#
# Nothing here is a macOS tool: no sips, iconutil, actool, xcrun, no GNU-coreutils aliases for BSD names, no xdg-open (the
# Linux box of a headless server has none; the plugin prints the path instead).
ARG DEBIAN_TAG=13.7-slim
ARG UV_VERSION=0.12.11

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM debian:${DEBIAN_TAG}
ARG NODE_VERSION=24.21.0
ARG NODE_SHA256_ARM64=6ad1325edbdb5649c379b75a237147a666c95d4f9ae8d340fef2d1575d289ad2
ARG NODE_SHA256_X64=fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8

# Tools the plugin documents (README, `brand-creator prereq`): Python 3.12+, resvg, ImageMagick (magick), Ghostscript, poppler,
# ripgrep, potrace, fonts. git and curl are what a developer machine has (the adoption survey reads git heads); xz-utils unpacks Node.
# The lib* packages are the shared libraries Chromium's headless shell links against (Playwright's list for Debian 13).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl xz-utils git bash coreutils findutils diffutils \
      python3 \
      resvg imagemagick ghostscript poppler-utils ripgrep potrace \
      fontconfig fonts-dejavu-core fonts-liberation2 fonts-noto-core \
      libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libcairo2 libcups2t64 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0t64 \
      libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -f >/dev/null

RUN set -eu; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in arm64) node_arch=arm64; node_sha="$NODE_SHA256_ARM64";; amd64) node_arch=x64; node_sha="$NODE_SHA256_X64";; *) echo "unsupported architecture $arch" >&2; exit 1;; esac; \
    f="node-v${NODE_VERSION}-linux-${node_arch}.tar.xz"; \
    curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/${f}"; \
    echo "${node_sha}  ${f}" | sha256sum -c -; \
    tar -xJf "$f" -C /usr/local --strip-components=1 --exclude='*.md' --exclude=LICENSE; \
    rm "$f"; \
    node --version; npm --version

COPY --from=uv /uv /uvx /usr/local/bin/

# A normal user, not root: permission-dependent behaviour (a read-only folder, a refused write) differs for root.
RUN useradd --create-home --home-dir /work/user --uid 1000 --shell /bin/bash bc \
 && mkdir -p /work && chown -R bc:bc /work
USER bc
WORKDIR /work
ENV HOME=/work/user UV_PYTHON_DOWNLOADS=never UV_NO_PROGRESS=1 PYTHONDONTWRITEBYTECODE=1

CMD ["bash"]
