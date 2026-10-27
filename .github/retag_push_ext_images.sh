#!/usr/bin/env bash
EXTRA_ARGS=$*
if [ -z "${ACR_REPO}" ]
then
  echo "Your must set ACR_REPO"
  exit 1
fi
if [ -z "${ORIG_REPO}" ]
then
  ORIG_REPO=docker.io/
fi
if [ -z "${HUB_DOCKER_REPO}" ]
then
  export HUB_DOCKER_REPO=${ORIG_REPO}
fi
# shellcheck disable=SC2086
IMGNAMES=$(docker compose -f docker-compose-local.yml ${EXTRA_ARGS} config --format json | jq -r '.services[].image' | sort | uniq)
IMGNAMES=$(echo "$IMGNAMES docker.io/willfarrell/autoheal:latest" | grep "${ORIG_REPO}")
for IMGNAME in $IMGNAMES
do
  # shellcheck disable=SC2001
  NEWNAME=$(echo "${IMGNAME}" | sed -e s%"${ORIG_REPO}"%"${ACR_REPO}/"%g)
  echo "buildx imagetools create --tag ${NEWNAME} ${IMGNAME}"
  docker buildx imagetools create --tag "${NEWNAME}" "${IMGNAME}"
  # If we got pvarki image from docker hub copy it to ghcr.io as well
  if grep -q '/pvarki/' <<<"$IMGNAME"; then
    # shellcheck disable=SC2001
    GHCRNAME=$(echo "${IMGNAME}" | sed -e s%"${ORIG_REPO}"%"ghcr.io/"%g)
    echo "buildx imagetools create --tag ${GHCRNAME} ${IMGNAME}"
    docker buildx imagetools create --tag "${GHCRNAME}" "${IMGNAME}"
  fi
done
