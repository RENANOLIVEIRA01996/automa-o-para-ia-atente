#!/bin/sh
set -eu

# O disco do Render é montado depois do build e pode encobrir o dono definido
# no Dockerfile. Prepare somente as pastas persistentes antes de baixar privilégios.
if [ "${WORKER_PROCESS:-false}" != "true" ]; then
    mkdir -p /data/fotos /data/fotos_paciente /data/logos
    for path in /data /data/fotos /data/fotos_paciente /data/logos; do
        if ! runuser -u recepia -- test -w "$path"; then
            chown recepia:recepia "$path"
        fi
    done
fi

exec runuser -u recepia -- "$@"
