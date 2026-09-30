#!/usr/bin/env bash
# Instala Git, OpenSSL, Docker Engine e Compose Plugin em Ubuntu 24.04 ARM64 ou AMD64.
# Execute na VM com: sudo bash scripts/oracle-setup.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Execute com sudo: sudo bash scripts/oracle-setup.sh" >&2
  exit 1
fi

# shellcheck disable=SC1091
. /etc/os-release
if [ "${ID:-}" != "ubuntu" ] || [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "Este script requer Ubuntu 24.04." >&2
  exit 1
fi
case "$(dpkg --print-architecture)" in
  arm64|amd64) ;;
  *) echo "Este script requer uma VM ARM64 ou AMD64." >&2; exit 1 ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git openssl

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

apt-get update
apt-get install -y --no-install-recommends \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker.service
systemctl enable --now containerd.service

docker --version
docker compose version
echo "Docker pronto. Configure o .env antes de iniciar os containers."
