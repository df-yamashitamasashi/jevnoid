#!/usr/bin/env bash
# Deploys the static site and Pages Function to production.
# The fallback snapshot (served when the Function's free daily quota is exhausted) is refreshed from KV first.
set -euo pipefail
cd "$(dirname "$0")"

npx --yes wrangler@4 kv key get snapshot --binding VITALS --remote 2>/dev/null > public/vitals-snapshot.json.tmp
python3 -c "import json; json.load(open('public/vitals-snapshot.json.tmp'))"
mv public/vitals-snapshot.json.tmp public/vitals-snapshot.json

npx --yes wrangler@4 pages deploy --branch main "$@"
