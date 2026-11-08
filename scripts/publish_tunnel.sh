#!/bin/bash
# Start a Cloudflare quick tunnel to the local backend (:8000) and point the GitHub Pages dashboard at it.
# The quick-tunnel URL changes every time, so run this whenever you restart the tunnel.
#   scripts/publish_tunnel.sh
set -euo pipefail
cd "$(dirname "$0")/.."
LOG=/tmp/lifeline-tunnel.log
pkill -f "cloudflared tunnel --no-autoupdate --url http://localhost:8000" 2>/dev/null || true
nohup cloudflared tunnel --no-autoupdate --url http://localhost:8000 > "$LOG" 2>&1 &
URL=""
for _ in $(seq 1 30); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done
[ -z "$URL" ] && { echo "Tunnel didn't start; see $LOG"; exit 1; }
echo "Tunnel: $URL"
WT=$(mktemp -d)/ghp
git fetch -q origin gh-pages
git worktree add -q "$WT" origin/gh-pages
printf '{"apiBase": "%s"}\n' "$URL" > "$WT/app/config.json"
(cd "$WT" && git add app/config.json && git commit -qm "Point dashboard at $URL" && git push -q origin HEAD:gh-pages)
git worktree remove --force "$WT"
echo "Published. Live in ~1 min: https://darthdextroy.github.io/Good-Neighbor-Triage/app/"
