#!/bin/bash
set -e

container_id=$(docker ps -aqf "name=backup")
docker exec -it "$container_id" ./backup.sh
