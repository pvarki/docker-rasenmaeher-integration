FROM caddy:builder AS builder
RUN xcaddy build \
      --with github.com/gr33nbl00d/caddy-revocation-validator \
    && true

FROM caddy:latest as production
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
