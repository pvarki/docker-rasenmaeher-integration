# Init container for Azure Container Apps volumes
FROM bash:latest AS configs
COPY entrypoint_deliver.sh /
COPY ./ /full_ctx
RUN chmod a+x /entrypoint_deliver.sh \
    && mkdir /dist \
    && cp -r /full_ctx/includes /dist/includes \
    && cp -r /full_ctx/templates* /dist/ \
    && mkdir /deliver \
    && true
ENTRYPOINT ["/entrypoint_deliver.sh"]

# Actual NGinx container
FROM nginx:1.29.3-alpine AS production
COPY entrypoint_templates.sh /
COPY crl_watcher.sh /usr/local/bin
RUN apk add --no-cache inotify-tools bash procps
ENTRYPOINT ["/entrypoint_templates.sh"]
CMD ["nginx", "-g", "daemon off;"]
