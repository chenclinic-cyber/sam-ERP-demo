#!/bin/bash
# 用法: TOKEN=ghp_xxx OWNER=chenclinic-cyber REPO=sam-ERP-demo bash deploy.sh
set -e
OWNER="${OWNER:-chenclinic-cyber}"
REPO="${REPO:-sam-ERP-demo}"
cd "$(dirname "$0")"

echo "==> push 到 $OWNER/$REPO ..."
git push "https://${OWNER}:${TOKEN}@github.com/${OWNER}/${REPO}.git" main:main -f

echo "==> 透過 API 開啟 GitHub Pages (main / root) ..."
curl -s -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/pages" \
  -d '{"source":{"branch":"main","path":"/"}}' -o /tmp/pages_resp.json -w "HTTP %{http_code}\n" || true
cat /tmp/pages_resp.json 2>/dev/null | head -c 400; echo

echo "==> 網址："
echo "https://${OWNER}.github.io/${REPO}/"
