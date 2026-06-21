#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ike App ランチャー
# このファイルを Finder でダブルクリックするとアプリが起動します
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Ike App を起動しています…"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  ブラウザが自動で開きます。"
echo "  止めるときは、この画面で Control + C を押してください。"
echo ""

# ローカル起動なのでパスワードゲートを無効化（自分のMac上）
export IKE_LOCAL=1

# 既に起動中なら停止してから起動（ポート重複回避）
lsof -ti:8501 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1

streamlit run app.py --server.port 8501
