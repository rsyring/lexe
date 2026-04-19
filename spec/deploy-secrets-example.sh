#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export OP_SERVICE_ACCOUNT_TOKEN="$(tr -d '\r\n' < /home/exedev/.config/1pass-svc-token.txt)"

if [[ -z "${OP_SERVICE_ACCOUNT_TOKEN}" ]]; then
  echo "ERROR: /home/exedev/.config/1pass-svc-token.txt is empty" >&2
  exit 1
fi

docker volume create syring-checks-hc-data >/dev/null
docker run --rm -v syring-checks-hc-data:/data busybox sh -c 'chown -R 999:999 /data && chmod 755 /data && [ ! -e /data/hc.sqlite ] || chmod 664 /data/hc.sqlite'

op run --env-file=./secrets.env -- docker compose up -d --remove-orphans --force-recreate web
