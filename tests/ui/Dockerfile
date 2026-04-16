# Dockerized Playwright runner for this repository.
# Builds dependencies once under /workspace/tests/ui/node_modules.

FROM mcr.microsoft.com/playwright:v1.49.0-noble

# Fonts used by the uiv2 design so screenshot captures match a local browser
ARG GEIST_VERSION=1.8.0
ARG GEIST_SHA256=ee309b6b0762f89c3e8a799f700bee0323315ff047df3a587af978f8180daa28

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        fonts-jetbrains-mono \
        fonts-liberation \
        fonts-noto-core \
        fonts-noto-color-emoji \
        fonts-dejavu-core \
        curl \
        unzip \
        ca-certificates; \
    rm -rf /var/lib/apt/lists/*; \
    mkdir -p /usr/local/share/fonts/geist-mono; \
    curl -fsSL -o /tmp/geist.zip \
        "https://github.com/vercel/geist-font/releases/download/${GEIST_VERSION}/geist-font-${GEIST_VERSION}.zip"; \
    echo "${GEIST_SHA256}  /tmp/geist.zip" | sha256sum -c -; \
    unzip -j /tmp/geist.zip \
        "geist-font-${GEIST_VERSION}/fonts/GeistMono/otf/*.otf" \
        -d /usr/local/share/fonts/geist-mono; \
    rm /tmp/geist.zip; \
    fc-cache -f

# Copy repository sources for test discovery.
WORKDIR /workspace
COPY . /workspace

RUN find /workspace -type d -name node_modules -prune -exec rm -rf '{}' +

# Install Playwright dependencies for this image.
WORKDIR /workspace/tests/ui
RUN npm ci --no-audit --no-fund
RUN ln -s /workspace/tests/ui/node_modules /workspace/node_modules
RUN npx playwright install chromium

ENTRYPOINT ["/workspace/tests/ui/node_modules/.bin/playwright", \
            "test", \
            "--config", "/workspace/tests/ui/playwright.config.ts"]
