# Setup
The Django server, Postgres DB, and hourly back-up of the DB are
performed using Docker containers. They are defined in `house-keeper.yml` 
in `../ansible/house-keeper` along with bash scripts to modify these containers. 

1. For storing local database back-ups, create the following folder:
   ```bash
   # for default images (debian)
   sudo mkdir -p /var/opt/pgbackups && sudo chown -R 999:999 /var/opt/pgbackups
   ```
   For a custom user and group set-up, change the last command to
   ```bash
   chown -R user:group /var/opt/pgbackups
   ```
   On a default Mac, for example, you can use your personal user account and the group `staff`.
   You might also have to adjust the directory permissions:
   ```bash
   # if possible, try to use stricter permissions like 775
   chmod -R 777 /var/opt/pgbackups
   ```
   
2. Use the run configuration `[house_keeper] start server`.

# Usage
## Start services
Use the run configuration `[house_keeper] start server`:
* It automatically creates an hourly back-up.
* Starts the container in detached mode `docker-compose up -d`

## ./docker scripts for development
* `create_and_apply_migration.sh` -- roll out DB changes without restarting services
* `create_db_backup.sh` -- manually create a back-up of the database
* `remove_container.sh` -- removes docker container(s) with specified name(s)
* `restore_django_db.sh` -- restore most recent back-up of django-db to container

## Access points
Django web server:

``` bash
http://localhost:8000
```
* There is an admin site accessible at `/admin`.

The Postgres DB can be accessed in your local terminal with:

```bash
psql -U postgres -p 5001 -h localhost -d house_keeper
```

# Troubleshooting
Use `docker ps -a` to find the relevant container id and see output with
`docker logs <container-id>`. It may be useful to use the command 
in `[house_keeper] start server` with various levels of verbosity to get more
output.