"""SSHPilot desktop launcher.

This is the PyInstaller entry point. It boots the FastAPI server on a local
port and opens the default browser. Closing the console window stops the app.
"""
import sys


def main() -> None:
    import socket
    import threading
    import time
    import webbrowser
    import urllib.request

    import uvicorn
    from app.main import app

    HOST = "127.0.0.1"

    def _find_free_port(preferred: int = 8000) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, preferred))
                return preferred
            except OSError:
                s.bind((HOST, 0))
                return s.getsockname()[1]

    def _open_browser_when_ready(port: int) -> None:
        url = f"http://{HOST}:{port}"
        for _ in range(50):
            try:
                urllib.request.urlopen(f"{url}/api/health", timeout=0.5)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        webbrowser.open(url)

    port = _find_free_port(8000)
    print("=" * 52)
    print("  SSHPilot — agentic terminal")
    print(f"  Running at http://{HOST}:{port}")
    print("  Keep this window open. Close it to quit.")
    print("=" * 52)
    threading.Thread(target=_open_browser_when_ready, args=(port,), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("\n" + "=" * 52)
        print("  SSHPilot crashed. Error details:")
        print("=" * 52)
        traceback.print_exc()
        print("\nPress Enter to close this window...")
        input()
        sys.exit(1)
