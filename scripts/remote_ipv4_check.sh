#!/usr/bin/env bash
# Is Docker Hub reachable over IPv4? Earlier tests only resolved an IPv6 address.
set -euo pipefail

# Real connection info lives in the untracked scripts/remote_env.local.sh
[ -f "$(dirname "$0")/remote_env.local.sh" ] && . "$(dirname "$0")/remote_env.local.sh" || true
KEY=${RRL_SSH_KEY:-$HOME/.ssh/id_ed25519}
HOST=${RRL_SERVER:-root@YOUR_SERVER_IP}

ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$HOST" 'bash -s' <<'REMOTE'
set -uo pipefail
echo "=== DNS records ==="
getent ahostsv4 registry-1.docker.io | head -3 || echo "no A record via getent"
getent ahostsv6 registry-1.docker.io | head -2 || echo "no AAAA record"
echo "=== IPv6 route? ==="
ip -6 route show default 2>/dev/null | head -2 || echo "no default ipv6 route"
echo "=== IPv4 reachability ==="
printf 'registry v4 : '; curl -4 -s -o /dev/null -w '%{http_code}\n' --max-time 12 https://registry-1.docker.io/v2/ 2>&1 || echo ERR
printf 'auth.docker.io v4 : '; curl -4 -s -o /dev/null -w '%{http_code}\n' --max-time 12 https://auth.docker.io/token 2>&1 || echo ERR
printf 'production.cloudflare v4 : '; curl -4 -s -o /dev/null -w '%{http_code}\n' --max-time 12 https://production.cloudflare.docker.com/ 2>&1 || echo ERR
echo "=== IPv6 reachability ==="
printf 'registry v6 : '; curl -6 -s -o /dev/null -w '%{http_code}\n' --max-time 8 https://registry-1.docker.io/v2/ 2>&1 || echo ERR
REMOTE
