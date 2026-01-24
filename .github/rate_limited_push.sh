#!/usr/bin/env bash
EXTRA_ARGS=$*

LASTIMG=""
push_tags() {
# shellcheck disable=SC2086
for IMGNAME in $(docker compose ${EXTRA_ARGS} config --format json | jq -r '.services[].image' | sort | uniq | grep '/pvarki/')
do
  if [ ! -z "${LASTIMG}" ]
  then
    sleep $((RANDOM % 5))
  fi
  if ! docker push ${IMGNAME}
  then
    return 1
  fi
  LASTIMG=$IMGNAME
done
}

# Try three times
push_tags || (sleep 10 && push_tags) || (sleep 10 && push_tags)
