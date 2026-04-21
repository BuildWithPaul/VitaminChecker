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

# ── 2. Create Caddyfile ─────────────────────────────────────────────
cat > Caddyfile << 'EOF'
paul-sandbox.duckdns.org {
	handle_path /vitaminchecker/* {
		reverse_proxy vitaminchecker:5000
	}
	redir /vitaminchecker /vitaminchecker/ permanent
	redir / /vitaminchecker/ permanent
}
EOF

# ── 3. Create production compose ─────────────────────────────────────
cat > docker-compose.prod.yml << 'EOF'
services:
  vitaminchecker:
    build: .
    container_name: vitaminchecker
    restart: unless-stopped
    environment:
      - FLASK_ENV=production
      - APPLICATION_ROOT=/vitaminchecker
    volumes:
      - ./uploads:/app/uploads

  caddy:
    image: caddy:2
    container_name: caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - vitaminchecker

volumes:
  caddy_data:
  caddy_config:
EOF

# ── 4. Build & start ─────────────────────────────────────────────────
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "✓ VitaminChecker deployed!"
echo "  URL: https://paul-sandbox.duckdns.org/vitaminchecker/"
echo ""
echo "Caddy auto-obtains + auto-renews Let's Encrypt certificates."
echo ""
echo "Commands:"
echo "  docker compose -f docker-compose.prod.yml logs -f caddy      # Caddy logs"
echo "  docker compose -f docker-compose.prod.yml logs -f vitaminchecker  # App logs"
echo "  docker compose -f docker-compose.prod.yml restart             # Restart all"
echo "  docker compose -f docker-compose.prod.yml down                 # Stop all"