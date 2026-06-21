#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Ike App — スタンドアロン化（ネイティブウィンドウ版＋ウィジェット版）
# 使い方: bash build_standalone_app.sh
# デスクトップに「Ike App」と「Ike Widget」を配置します。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(which python3)"
DESKTOP="$HOME/Desktop"

build_app () {
    local APP_NAME="$1"; local SCRIPT="$2"; local AGENT="$3"
    local APP="$DESKTOP/$APP_NAME.app"
    rm -rf "$APP"
    mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

    cat > "$APP/Contents/MacOS/launcher" << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
exec "$PYTHON" "$SCRIPT"
EOF
    chmod +x "$APP/Contents/MacOS/launcher"

    [ -f "$SCRIPT_DIR/assets/IkeApp.icns" ] && cp "$SCRIPT_DIR/assets/IkeApp.icns" "$APP/Contents/Resources/AppIcon.icns"

    cat > "$APP/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>CFBundleName</key><string>$APP_NAME</string>
    <key>CFBundleDisplayName</key><string>$APP_NAME</string>
    <key>CFBundleIdentifier</key><string>com.ikemoto.${APP_NAME// /}</string>
    <key>CFBundleVersion</key><string>1.0</string>
    <key>CFBundleExecutable</key><string>launcher</string>
    <key>CFBundleIconFile</key><string>AppIcon</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>LSMinimumSystemVersion</key><string>10.13</string>
    <key>NSHighResolutionCapable</key><true/>
    ${AGENT:+<key>LSUIElement</key><true/>}
</dict></plist>
EOF
    touch "$APP"
    echo "  ✅ $APP_NAME → デスクトップ"
}

echo "Ike App をネイティブアプリ化しています…"
build_app "Ike App" "native_app.py"
build_app "Ike Widget" "widget_app.py"
build_app "Ike Menu" "menubar_app.py" "agent"
echo ""
echo "完了。デスクトップの「Ike App」（本体）と「Ike Widget」（小窓）をダブルクリックで起動できます。"
echo "初回のみ: 右クリック →「開く」→「開く」で許可してください（未署名アプリのため）。"
