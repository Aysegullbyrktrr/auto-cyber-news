# Deployment — 24/7 on a Linux Server (Docker)

Run `auto-cyber-news` continuously on a Linux VPS with Docker Compose. The
scheduler does everything on a loop (default every 60 min): ingest → dedup →
enrich → incidents → Telegram alerts → once-per-day email digest. It restarts
automatically on crash and on server reboot.

> No public ports are opened — the app only makes outbound calls (RSS, Gemini,
> Telegram, SMTP). Nothing listens for inbound traffic.

---

## 1. Install Docker (once, on the server)

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker      # start Docker on boot
# optional: run docker without sudo
sudo usermod -aG docker "$USER" && newgrp docker
```

## 2. Get the code onto the server

**With git:**
```bash
git clone <your-repo-url> auto-cyber-news
cd auto-cyber-news
```

**Without git (copy from your PC):** from your machine, send the project but
**exclude** the local virtualenv and data:
```bash
rsync -av --exclude '.venv' --exclude 'data' --exclude '.git' \
  ./auto-cyber-news/  user@server:/home/user/auto-cyber-news/
```

## 3. Configure secrets

```bash
cp .env.example .env
nano .env            # fill in the values below
chmod 600 .env       # restrict to your user
```

Set in `.env`:
```ini
TELEGRAM_BOT_TOKEN=...        # from @BotFather (rotate if it was ever shared)
TELEGRAM_CHAT_ID=...
GEMINI_API_KEY=...            # or ANTHROPIC_API_KEY; omit for rule-based summaries
SUMMARY_LANGUAGE=Turkish      # optional
ALERTS_DRY_RUN=false          # true = process but don't send (use for a first dry run)
# Email digest (optional):
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EMAIL_FROM=
EMAIL_TO=
```

## 4. Start it (24/7)

```bash
docker compose up -d --build
```

That's it — it's now running and will survive reboots (`restart: unless-stopped`
+ Docker enabled on boot). The SQLite database lives in a Docker-managed named
volume (`acn-data`), so the non-root container user can write it without any
host permission setup.

## 5. Verify

```bash
docker compose ps                       # STATUS should become "healthy"
docker compose logs -f                  # watch cycles (JSON logs)
docker compose exec auto-cyber-news auto-cyber-news health-check
docker compose exec auto-cyber-news auto-cyber-news db-status
```

Optional first seed (so you don't wait for the first interval):
```bash
docker compose exec auto-cyber-news auto-cyber-news run-once
```

---

## Operations

**Tuning (in `.env`, then `docker compose up -d`):**

| Variable | Default | Meaning |
| --- | --- | --- |
| `SCHEDULER_INTERVAL_MINUTES` | 60 | Cycle cadence |
| `RETENTION_DAYS` | 30 | Prune processed/alert rows older than this |
| `ALERT_COOLDOWN_HOURS` | 6 | Min gap before re-alerting the same incident |
| `ALERTS_DRY_RUN` | false | `true` = no Telegram/email sent |

**Update to new code:**
```bash
git pull            # or rsync again
docker compose up -d --build
```

**Backup the database** (the only state worth keeping — it's in the `acn-data`
named volume):
```bash
docker compose exec auto-cyber-news \
  sh -c 'sqlite3 /app/data/auto-cyber-news.db ".backup /app/data/backup.db"'
docker compose cp auto-cyber-news:/app/data/backup.db ./acn-backup-$(date +%F).db
```

**Logs / stop / start:**
```bash
docker compose logs --since 1h
docker compose stop          # pause (keeps data + container)
docker compose start
docker compose down          # remove container (data/ volume kept on host)
```

---

## Alternative: systemd (no Docker)

If you prefer running on the host directly, the repo ships a unit at
`deploy/auto-cyber-news.service` and a secrets template at
`deploy/auto-cyber-news.env.example`. Flow: create a venv under
`/opt/auto-cyber-news`, install the package, drop secrets into
`/etc/auto-cyber-news/auto-cyber-news.env` (root, `chmod 600`), then
`systemctl enable --now auto-cyber-news`. Docker is recommended for simplicity.
