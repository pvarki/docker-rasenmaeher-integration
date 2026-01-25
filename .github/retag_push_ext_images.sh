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
export HUB_DOCKER_REPO=${ORIG_REPO}
# shellcheck disable=SC2086
for IMGNAME in $(docker compose ${EXTRA_ARGS} config --format json | jq -r '.services[].image' | sort | uniq | grep "${ORIG_REPO}")
do
  # shellcheck disable=SC2001
  NEWNAME=$(echo "${IMGNAME}" | sed -e s%"${ORIG_REPO}"%"${ACR_REPO}/"%g)
  echo "docker image tag ${IMGNAME} ${NEWNAME}"
  docker image tag "${IMGNAME}" "${NEWNAME}"
  docker push "${NEWNAME}"
done
