"""Ike App — ネイティブウィンドウ版（ブラウザのタブではなく独立アプリとして起動）
内部で Streamlit を起動し、pywebview のネイティブウィンドウに表示する。
ウィンドウを閉じると Streamlit も終了する。

起動: python native_app.py
"""
import os
import sys
import time
import socket
import subprocess
import atexit

DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8501


def _port_open(p):
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", p))
        return True
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

    # ローカル起動なのでパスワードゲートを無効化（自分のMac上）。子のstreamlitへ継承される。
    os.environ["IKE_LOCAL"] = "1"

    # 既存の8501を掃除
    if _port_open(PORT):
        subprocess.run("lsof -ti:%d | xargs kill -9" % PORT, shell=True)
        time.sleep(1)

    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", str(PORT), "--server.headless", "true",
         "--server.address", "0.0.0.0",  # iPhone等から同一WiFiでアクセス可能に
         "--server.enableXsrfProtection", "false",
         "--browser.gatherUsageStats", "false"],
        cwd=DIR)
    atexit.register(lambda: proc.terminate())

    # 起動待ち
    for _ in range(80):
        if _port_open(PORT):
            break
        time.sleep(0.5)

    webview.create_window("Ike App", f"http://localhost:{PORT}",
                          width=1440, height=920, min_size=(1000, 700))
    webview.start()  # ウィンドウが閉じるまでブロック
    proc.terminate()


if __name__ == "__main__":
    main()
