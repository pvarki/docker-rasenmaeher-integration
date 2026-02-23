FROM python:3.11-slim AS deps

# Install OS-level packages
RUN apt-get update && apt-get install -y \
      ca-certificates \
      curl \
      gettext \
      openssl \
      tini \
      vim \
      jq \
      netcat-openbsd \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && curl https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh -o /usr/bin/wait-for-it.sh \
    && chmod a+x /usr/bin/wait-for-it.sh \
    && true
RUN pip install --no-cache-dir authlib psycopg2-binary matrix-synapse

WORKDIR /opt/synapse
COPY scripts ./scripts
COPY templates ./templates
RUN chmod +x /opt/synapse/scripts/*.sh

FROM deps AS run
WORKDIR /opt/synapse
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/synapse/scripts/synapse-entrypoint.sh"]