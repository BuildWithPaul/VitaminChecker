#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# VitaminChecker deployment with auto-HTTPS (Caddy + Docker)
# Domain: paul-sandbox.duckdns.org/vitaminchecker
#
# PREREQUISITES (run on your VPS):
#   1. Docker + Docker Compose installed
#   2. paul-sandbox.duckdns.org DNS → your VPS public IP
#   3. Ports 80, 443 open (for Let's Encrypt HTTP-01 challenge)
# ─────────────────────────────────────────────────────────────────────

set -e

# ── 1. Clone ─────────────────────────────────────────────────────────
if [ -d "$HOME/vitaminchecker" ]; then
    cd ~/vitaminchecker && git pull
else
    git clone https://github.com/BuildWithPaul/VitaminChecker.git ~/vitaminchecker
    cd ~/vitaminchecker
fi

# ── 2. Build & start ─────────────────────────────────────────────────
docker compose -f deploy/docker-compose.prod.yml up -d --build

echo ""
echo "✓ VitaminChecker deployed!"
echo "  URL: https://paul-sandbox.duckdns.org/vitaminchecker/"
echo ""
echo "Caddy auto-obtains + auto-renews Let's Encrypt certificates."
echo ""
echo "Commands:"
echo "  docker compose -f deploy/docker-compose.prod.yml logs -f caddy           # Caddy logs"
echo "  docker compose -f deploy/docker-compose.prod.yml logs -f vitaminchecker   # App logs"
echo "  docker compose -f deploy/docker-compose.prod.yml restart                  # Restart all"
echo "  docker compose -f deploy/docker-compose.prod.yml down                     # Stop all"