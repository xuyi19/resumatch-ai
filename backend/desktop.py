"""ResuMatch AI 桌面版启动器（PyInstaller one-folder 入口）。

- 端口探测用 SO_EXCLUSIVEADDRUSE（Windows 下 SO_REUSEADDR 会误判被占端口为空闲，
  导致浏览器打开别人应用的端口——如 8765 被蓝笔申论占用时的串台）
- pywebview 原生窗口优先，未安装/`--browser` 时回退浏览器；`--no-browser` 仅起服务（烟测用）
- 单实例复用：重复双击直接为已有实例开窗口
- --windowed 无控制台打包：stdout/stderr 置空时日志落 data/logs/app.log
"""
import os
import socket
import sys
import threading
import time
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def _setup_logging() -> Path | None:
    """windowed 打包下 stdout/stderr 为 None：先垫 devnull 防炸，再落文件日志。"""
    windowed = getattr(sys, "stdout", None) is None or getattr(sys, "stderr", None) is None
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115
    if not windowed:
        return None  # 有控制台时日志直接可见，无需文件
    log_file = _base_dir() / "data" / "logs" / "app.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        from loguru import logger

        logger.add(log_file, rotation="2 MB", retention=5, encoding="utf-8", level="INFO")
        return log_file
    except Exception:
        return None


def _log(msg: str) -> None:
    try:
        from loguru import logger

        logger.info(msg)
    except Exception:
        pass


def _port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            if sys.platform == "win32":
                # Windows：SO_REUSEADDR 允许绑定他人已占端口（误判空闲 + 串台），
                # 必须用 SO_EXCLUSIVEADDRUSE 才能真正探活
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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


def _health_is_resumatch(port: int) -> bool:
    """确认该端口响应的是 ResuMatch（防止同端口被其它应用抢答）。"""
    try:
        import httpx

        r = httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=1.0)
        return r.status_code == 200 and "ResuMatch AI" in r.text
    except Exception:
        return False


def _find_running_port(preferred: int = 8765, span: int = 50) -> int | None:
    """扫描顺延区间找已在运行的 ResuMatch（不能只看 8765：
    8765 常被其它应用占用，本应用会顺延到 8766+，硬编码端口会漏判并重复启动）。"""
    for p in range(preferred, preferred + span):
        if _health_is_resumatch(p):
            return p
    return None


def _wait_ready(port: int, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _health_is_resumatch(port):
            return True
        time.sleep(0.3)
    return False


def _serve(app, port: int) -> None:
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    uvicorn.Server(config).run()


def _open_window(port: int) -> None:
    """pywebview 原生窗口优先；未安装则回退浏览器。必须在主线程调用。"""
    url = f"http://127.0.0.1:{port}/"
    try:
        import webview

        webview.create_window(
            "ResuMatch AI · 智能简历诊断",
            url,
            width=1280,
            height=860,
            min_size=(1080, 720),
        )
        webview.start()  # 阻塞至窗口关闭
    except Exception as e:
        _log(f"原生窗口不可用（{e}），回退浏览器打开。")
        import webbrowser

        webbrowser.open(url)


def main() -> None:
    _setup_logging()
    no_browser = "--no-browser" in sys.argv
    force_browser = "--browser" in sys.argv

    existing = _find_running_port()
    if existing is not None:
        _log(f"ResuMatch AI 已在运行（端口 {existing}），直接为已有实例打开窗口。")
        if not no_browser:
            _open_window(existing)  # 主线程阻塞，窗口关闭即退出
        return

    port = _pick_port()
    from app.main import app  # 延迟导入，端口探测阶段保持轻量

    threading.Thread(target=_serve, args=(app, port), daemon=True).start()

    if not _wait_ready(port):
        _log(f"服务在 {port} 端口启动失败，请查看 data/logs/app.log")
        if no_browser:  # 烟测模式：让失败可被脚本观测
            sys.exit(1)
        return

    _log(f"服务就绪：http://127.0.0.1:{port}/")
    if no_browser:
        _hold()  # 烟测模式：无窗口，保持服务运行
        return

    if force_browser:
        import webbrowser

        webbrowser.open(f"http://127.0.0.1:{port}/")
        _hold()
        return

    # 原生窗口：阻塞在 webview.start()，窗口关闭即退出（uvicorn 为 daemon 线程）
    _open_window(port)
    _log("窗口已关闭，进程退出。")


def _hold() -> None:
    """无窗口模式（--no-browser/--browser）保持服务运行。"""
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
