#!/bin/bash
set -e

container_id=$(docker ps -aqf "name=django")
docker exec -it "$container_id" python manage.py makemigrations
docker exec -it "$container_id" python manage.py migrate

dot="$(cd "$(dirname "$0")"; pwd)"
path="$dot/../../house-keeper/house_keeper/cleaner/migrations/*"
sudo chown "$USER":"$USER" -R $path
