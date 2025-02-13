#!/bin/bash
set -ex
cp -r /nginx_templates/$NGINX_TEMPLATE_DIR /etc/nginx/templates
cp -r /nginx_templates/includes /etc/nginx/includes

. /docker-entrypoint.sh
