#!/bin/bash
set -e

function find_and_remove_container() {
  container_id=$(docker ps -aqf "name=$1")
  if [ -z "$container_id" ]; then
    echo "could not find container name=$1"
  else
    docker container rm -f "$container_id"
    echo "remove container name=$1 (container_id=$container_id)"
  fi
}

for var in "$@"; do
  find_and_remove_container "$var"
done
