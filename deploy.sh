#!/bin/bash
# 用法: TOKEN=ghp_xxx OWNER=chenclinic-cyber REPO=sam-ERP-demo bash deploy.sh
# 第一次執行請指定本機名稱，例如: NB="診所 NB" TOKEN=ghp_xxx bash deploy.sh
# 名稱會記在 .nb_name（僅存本機，不會上傳），之後直接 TOKEN=ghp_xxx bash deploy.sh 即可
set -e
OWNER="${OWNER:-chenclinic-cyber}"
REPO="${REPO:-sam-ERP-demo}"
cd "$(dirname "$0")"

# ==> 本機名稱（顯示在網頁標題與頁首，讓 iPhone 分得出是哪台電腦推的）
if [ -n "$NB" ]; then
  printf '%s' "$NB" > .nb_name
fi
if [ -f .nb_name ]; then
  NB_NAME="$(cat .nb_name)"
else
  read -r -p "請輸入這台電腦的名稱（例如 診所 NB / 住家 NB）： " NB_NAME
  printf '%s' "$NB_NAME" > .nb_name
fi
echo "==> 本機名稱：$NB_NAME"

printf 'window.NB_NAME="%s";\n' "$NB_NAME" > device.js
git add device.js
git commit -m "更新來源電腦：$NB_NAME" >/dev/null 2>&1 || true

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
