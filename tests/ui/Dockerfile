# Dockerized Playwright runner for this repository.
# Builds dependencies once under /workspace/tests/ui/node_modules.

FROM mcr.microsoft.com/playwright:v1.49.0-noble

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
