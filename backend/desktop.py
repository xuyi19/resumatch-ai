"""ResuMatch AI 桌面版启动器（PyInstaller one-folder 入口）。

- 端口探测 + 单实例复用（重复双击不启第二份）
- 等端口真正可连再开浏览器，避免白屏
- 保留 --no-browser 方便自动化烟测
"""
import os
import socket
import sys
import threading

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _pick_port(preferred: int = 8765, span: int = 50) -> int:
    for p in range(preferred, preferred + span):
        if _port_free(p):
            return p
    with socket.socket() as s:  # 顺延范围也满则交给系统分配
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _already_running(port: int) -> bool:
    """重复双击时复用已有实例。"""
    try:
        import httpx

        r = httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=1.0)
        return r.status_code == 200 and "ResuMatch AI" in r.text
    except Exception:
        return False


def _open_when_ready(port: int, timeout: float = 15.0) -> None:
    import time

    import webbrowser

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            import httpx

            if httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=1.0).status_code == 200:
                webbrowser.open(f"http://127.0.0.1:{port}/")
                return
        except Exception:
            time.sleep(0.3)
    # 超时也尝试打开一次，避免静默无窗口
    try:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    except Exception:
        pass


def main() -> None:
    if _already_running(8765):
        print("ResuMatch AI 已在运行，已为你打开已有窗口。")
        threading.Thread(target=lambda: _open_when_ready(8765), daemon=True).start()
        # 给浏览器一点时间，然后退出当前实例
        import time

        time.sleep(1.5)
        return

    port = _pick_port()
    from app.main import app  # 延迟导入，端口探测阶段保持轻量

    if "--no-browser" not in sys.argv:
        threading.Thread(target=_open_when_ready, args=(port,), daemon=True).start()

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
