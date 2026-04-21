# VitaminChecker — HTTPS Deployment Guide

Host at **https://paul-sandbox.duckdns.org/vitaminchecker/**
Auto-renewing Let's Encrypt cert via Caddy.

---

## Architecture

```
Browser → Caddy (443/HTTPS) → VitaminChecker Flask (5000)
              │
              └─ auto-obtains + renews Let's Encrypt cert
```

Caddy strips `/vitaminchecker` prefix, Flask runs at root inside container.

---

## Step 1: VPS Setup

Need a VPS with public IP (Hetzner, OVH, DigitalOcean, etc.)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in

# Verify
docker --version
docker compose version
```

## Step 2: DNS

Point `paul-sandbox.duckdns.org` → your VPS public IP.

For DuckDNS: go to https://www.duckdns.org, add/update domain with your VPS IP.

## Step 3: Open Firewall

```bash
# UFW (Ubuntu)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Or iptables
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

## Step 4: Clone & Deploy

```bash
git clone https://github.com/BuildWithPaul/VitaminChecker.git ~/vitaminchecker
cd ~/vitaminchecker

# Edit deploy/Caddyfile if you want a different domain or subpath
# Edit deploy/docker-compose.prod.yml if needed

docker compose -f deploy/docker-compose.prod.yml up -d --build
```

## Step 5: Verify

```bash
# Check containers are running
docker compose -f deploy/docker-compose.prod.yml ps

# Test external (after DNS propagates)
curl -s https://paul-sandbox.duckdns.org/vitaminchecker/ | head -5
```

---

## How It Works

| Component | Role |
|-----------|------|
| **Caddy** | Reverse proxy, auto-HTTPS, strips `/vitaminchecker` prefix |
| **APPLICATION_ROOT** | Flask env var. Makes `url_for()` generate `/vitaminchecker/...` paths |
| **APP_PREFIX** | JS window variable. Makes `fetch('/analyze')` → `fetch('/vitaminchecker/analyze')` |

Caddy's `handle_path` strips `/vitaminchecker` before forwarding to Flask.
Browser sends `/vitaminchecker/analyze` → Caddy forwards `/analyze` → Flask handles it.
Static assets: browser requests `/vitaminchecker/static/app.js` → Caddy forwards `/static/app.js` → Flask serves it.

---

## Certificate Auto-Renewal

Caddy handles this automatically. No cron, no certbot.

- Certificate obtained on first request
- Renewed ~30 days before expiry
- No downtime (Caddy uses SNI + hot-swap)

---

## Useful Commands

```bash
# View logs
docker compose -f deploy/docker-compose.prod.yml logs -f

# Restart
docker compose -f deploy/docker-compose.prod.yml restart

# Update app (pull latest code + rebuild)
cd ~/vitaminchecker && git pull
docker compose -f deploy/docker-compose.prod.yml up -d --build

# Stop
docker compose -f deploy/docker-compose.prod.yml down

# Check certificate
docker exec caddy caddy list-modules | grep tls
```

---

## Troubleshooting

**Certificate fails?**
- DNS not pointing to VPS yet → wait for propagation
- Port 80 blocked → check firewall
- DuckDNS TTL → can take a few minutes

**502 Bad Gateway?**
- Flask container not running → `docker compose -f deploy/docker-compose.prod.yml logs vitaminchecker`
- Flask not listening on 5000 → check Dockerfile CMD

**Static assets 404?**
- APPLICATION_ROOT must equal `/vitaminchecker`
- Check `<script>` tag uses `url_for('static', filename='app.js')`