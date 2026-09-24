"""知岗 ResuMatch-AI 桌面版启动器（PyInstaller one-folder 入口）。

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

        r = httpx.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=1.5,
                      trust_env=False)  # 不走系统代理，避免 localhost 请求被代理拖慢
        return r.status_code == 200 and "ResuMatch" in r.text
    except Exception:
        return False


def _find_running_port(preferred: int = 8765, span: int = 50) -> int | None:
    """扫描顺延区间找已在运行的 ResuMatch。

    必须先用 bind 探测短路：本机对「已关闭端口」做 TCP 连接不会立刻拒绝，
    而是静默挂到超时，逐个端口发 HTTP 请求探测 50 个端口要白等 50 秒（实测启动 52s）。
    bind 是纯本地操作，瞬时返回，只有被真正占用的端口才值得去 connect 验证身份。
    """
    for p in range(preferred, preferred + span):
        if _port_free(p):
            continue  # 无监听，不可能是 ResuMatch
        if _health_is_resumatch(p):
            return p
    return None


def _wait_ready(port: int, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        # 端口还没监听时不要去 connect：本机对关闭端口会挂满超时，白等
        if not _port_free(port) and _health_is_resumatch(port):
            return True
        time.sleep(0.2)
    return False


def _serve(app, port: int) -> None:
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    uvicorn.Server(config).run()


class DesktopApi:
    """pywebview js_api 桥：前端经 window.pywebview.api 调用。

    - pick_save_path：原生「另存为」对话框，返回用户选择的绝对路径（取消返回 None）
    - reveal_file：资源管理器打开并选中文件（导出历史「打开所在位置」用）
    """

    def pick_save_path(self, default_name: str = "优化后的简历.docx") -> str | None:
        import webview

        result = webview.windows[0].create_file_dialog(
            webview.SAVE_DIALOG, save_filename=default_name or "优化后的简历.docx"
        )
        if isinstance(result, (list, tuple)):
            result = result[0] if result else None
        return str(result) if result else None

    def reveal_file(self, path: str) -> bool:
        import subprocess

        p = str(path or "").strip()
        if not p or not Path(p).exists():
            return False
        if sys.platform == "win32":
            # 资源管理器打开并选中该文件
            subprocess.Popen(["explorer", "/select,", p])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", p])
        else:
            subprocess.Popen(["xdg-open", str(Path(p).parent)])
        return True


def _open_window(port: int) -> None:
    """pywebview 原生窗口优先；未安装则回退浏览器。必须在主线程调用。"""
    url = f"http://127.0.0.1:{port}/"
    try:
        import webview

        webview.create_window(
            "知岗 ResuMatch-AI · 简历岗位智能匹配诊断",
            url,
            width=1280,
            height=860,
            min_size=(1080, 720),
            js_api=DesktopApi(),
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
        _log(f"知岗 ResuMatch-AI 已在运行（端口 {existing}），直接为已有实例打开窗口。")
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
    # M22 C2：后台线程检查新版本（只提示不打扰，任何异常静默跳过）
    threading.Thread(target=_check_update, args=(port,), daemon=True).start()
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


def _check_update(port: int, timeout: float = 5.0):
    """M22 C2：请求仓库 VERSION 与本地版本对比，有新版则弹原生提示。

    只提示不自动下载；网络不通/仓库不可达时完全静默。
    """
    import urllib.request

    try:
        from app import __version__

        # 服务端 /api/v1/health 之类不提供版本，本地直接用包版本
        local = tuple(int(x) for x in __version__.split(".")[:3] if x.isdigit())
        sources = [
            "https://gitee.com/raw/master/VERSION",  # 占位：发布时替换为实际仓库路径
            "https://raw.githubusercontent.com/master/VERSION",
        ]
        remote = None
        for url in sources:
            try:
                with urllib.request.urlopen(url, timeout=timeout) as r:
                    remote_text = r.read().decode("utf-8").strip()
                remote = tuple(int(x) for x in remote_text.split(".")[:3] if x.isdigit())
                break
            except Exception:
                continue
        if remote and remote > local:
            _log(f"发现新版本 {remote_text}（当前 {__version__}）")
            _notify_update(__version__, remote_text)
    except Exception as e:
        _log(f"更新检查跳过: {e}")


def _notify_update(current: str, latest: str):
    """更新提示：优先 webview 原生弹窗，失败落日志。"""
    try:
        import webview

        webview.create_window(
            "发现新版本",
            html=(
                f"<body style='font-family:sans-serif;padding:24px;text-align:center'>"
                f"<h2>知岗 ResuMatch-AI 有新版本</h2>"
                f"<p>当前 {current} → 最新 {latest}</p>"
                f"<p style='color:#888'>请到发布页下载新版本（本次不自动更新）</p>"
                f"</body>"
            ),
            width=420, height=240, on_top=True,
        )
        webview.start()
    except Exception as e:
        _log(f"更新弹窗失败: {e}")


def _hold() -> None:
    """无窗口模式（--no-browser/--browser）保持服务运行。"""
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
