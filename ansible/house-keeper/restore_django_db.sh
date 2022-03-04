#!/bin/bash
set -e

BACKUP_FILE=/var/opt/pgbackups/daily/house_keeper-latest.sql.gz
LOCAL_BACKUP_FILE=backup.sql
if test -f "$BACKUP_FILE"; then
  rm -f $LOCAL_BACKUP_FILE
  cp -L "$BACKUP_FILE" "${LOCAL_BACKUP_FILE}.gz"
  gunzip "${LOCAL_BACKUP_FILE}.gz"
  psql -v ON_ERROR_STOP=0 -U "postgres" -p 5001 -h localhost -d "house_keeper" <$LOCAL_BACKUP_FILE
  echo "django db restored"
else
  echo "$BACKUP_FILE does not exist"
fi
