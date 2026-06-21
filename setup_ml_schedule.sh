#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ike App — ローカルML 定期実行セットアップ（macOS launchd）
# 毎日 深夜2:30 に エクスポート→学習→アプリ反映 を自動実行
# 使い方: bash setup_ml_schedule.sh
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=$(which python3)
PLIST_NAME="com.ikeapp.ml_train"
PLIST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_DIR="$SCRIPT_DIR/logs"; mkdir -p "$LOG_DIR"

# エクスポート→学習を順に実行するラッパー
RUNNER="$SCRIPT_DIR/run_ml_pipeline.sh"
cat > "$RUNNER" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
"$PYTHON" export_data.py
"$PYTHON" train_local.py
EOF
chmod +x "$RUNNER"

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key><string>${PLIST_NAME}</string>
    <key>ProgramArguments</key><array>
        <string>/bin/bash</string><string>${RUNNER}</string>
    </array>
    <key>WorkingDirectory</key><string>${SCRIPT_DIR}</string>
    <key>StartCalendarInterval</key><dict>
        <key>Hour</key><integer>2</integer><key>Minute</key><integer>30</integer>
    </dict>
    <key>StandardOutPath</key><string>${LOG_DIR}/ml.log</string>
    <key>StandardErrorPath</key><string>${LOG_DIR}/ml_error.log</string>
    <key>RunAtLoad</key><false/>
</dict></plist>
EOF

launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
echo "✅ ローカルML 定期実行を設定しました（毎日 2:30）"
echo "  手動実行: bash $RUNNER"
echo "  ログ:     tail -f $LOG_DIR/ml.log"
echo "  停止:     launchctl unload $PLIST"
