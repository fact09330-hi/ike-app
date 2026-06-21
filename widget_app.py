"""Ike App — デスクトップ・ウィジェット（常時最前面の小窓）
今日の負荷・予定・やることだけをコンパクトに、画面の隅に置ける小窓で表示。
内部で Streamlit を起動し、?view=widget の画面を pywebview の小窓で出す。

起動: python widget_app.py
"""
import os
import sys
import time
import socket
import subprocess
import atexit

DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8502  # 本体(8501)と別ポート


def _port_open(p):
    s = socket.socket(); s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", p)); return True
    except Exception:
        return False
    finally:
        s.close()


def main():
    try:
        import webview
    except ImportError:
        print("pywebview が必要です: pip install pywebview")
        sys.exit(1)

    # ローカル起動なのでパスワードゲートを無効化（枠なし小窓にログイン画面が出ないように）
    os.environ["IKE_LOCAL"] = "1"

    if not _port_open(PORT):
        proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py",
             "--server.port", str(PORT), "--server.headless", "true",
             "--browser.gatherUsageStats", "false"],
            cwd=DIR)
        atexit.register(lambda: proc.terminate())
        for _ in range(80):
            if _port_open(PORT):
                break
            time.sleep(0.5)

    # 常時最前面・枠なしの小窓 ＝ ウィジェット（グラフ＋カレンダーが入る縦長）
    webview.create_window(
        "Ike Widget", f"http://localhost:{PORT}/?view=widget",
        width=420, height=820, on_top=True, frameless=True,
        easy_drag=True, x=40, y=60)
    webview.start()


if __name__ == "__main__":
    main()
