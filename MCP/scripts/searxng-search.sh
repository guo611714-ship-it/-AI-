#!/bin/bash
# SearXNG search with auto-proxy start
# Usage: bash searxng-search.sh "search query" [language] [categories]

QUERY="${1:-test}"
LANG="${2:-zh-CN}"
CATEGORIES="${3:-general}"
PROXY_PORT=8001
SEARXNG_URL="http://localhost:8889"
HOLYTECH_EXE="D:\\holytech\\HolyTech.exe"

# Check if proxy is running
check_proxy() {
    netstat -an 2>/dev/null | grep -q "LISTENING.*:${PROXY_PORT}"
}

# Start HolyTech if proxy not running
start_proxy() {
    echo "[searxng] Proxy not running, starting HolyTech..." >&2
    start "" "$HOLYTECH_EXE" 2>/dev/null

    # Wait up to 15 seconds for proxy to start
    for i in $(seq 1 15); do
        sleep 1
        if check_proxy; then
            echo "[searxng] Proxy started on port ${PROXY_PORT}" >&2
            return 0
        fi
    done
    echo "[searxng] WARNING: Proxy failed to start, using direct connection" >&2
    return 1
}

# Main
if ! check_proxy; then
    start_proxy
fi

# URL-encode query
ENCODED_QUERY=$(python -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))" 2>/dev/null || echo "$QUERY")

# Execute search
RESULT=$(curl -s --max-time 10 \
    "${SEARXNG_URL}/search?q=${ENCODED_QUERY}&format=json&categories=${CATEGORIES}&language=${LANG}" 2>/dev/null)

# Check if we got results
if [ -z "$RESULT" ]; then
    echo "[searxng] Search returned empty, retrying without proxy..." >&2
    RESULT=$(curl -s --max-time 10 --noproxy '*' \
        "${SEARXNG_URL}/search?q=${ENCODED_QUERY}&format=json&categories=${CATEGORIES}&language=${LANG}" 2>/dev/null)
fi

# Parse and output results
echo "$RESULT" | python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    results = d.get('results', [])
    unresponsive = d.get('unresponsive_engines', [])
    print(f'Found {len(results)} results')
    if unresponsive:
        engines = [e[0] for e in unresponsive]
        print(f'Unresponsive: {', '.join(engines)}')
    for i, r in enumerate(results[:5]):
        print(f'{i+1}. {r[\"title\"][:80]}')
        print(f'   {r[\"url\"]}')
        content = (r.get('content') or '')[:200]
        if content:
            print(f'   {content}')
        print()
except Exception as e:
    print(f'Parse error: {e}')
" 2>/dev/null
