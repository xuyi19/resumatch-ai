"""
ResuMatch AI 一键启动脚本（开发联调用）
使用方法：python run.py

- 服务运行在两个独立控制台窗口（日志保持安静）
- 自动弹出独立浏览器实例；浏览器窗口全部关闭且页面心跳消失 = 自动停止全部服务
- 主窗口 Ctrl+C 或直接关闭，同样自动终止全部子进程（Job Object 兜底，无残留）
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

# ========== 配置 ==========
ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

# ★ conda 环境 python 绝对路径（项目固定环境，不可改名）
CONDA_PYTHON = r"E:\conda\envs\resumatch-ai\python.exe"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173

APP_URL = f"http://localhost:{FRONTEND_PORT}"

# 浏览器候选（按优先级）：独立实例启动，进程句柄可控、可等待退出
BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

BROWSER_PROFILE = Path(tempfile.gettempdir()) / "resumatch_browser_profile"

# 页面心跳阈值（秒）：浏览器进程退出后，若仍有页面在用（前端每 20s 上报一次心跳），
# 继续维持服务；心跳超过该秒数无更新才判定「真的没人用了」。
# 90s 可覆盖后台标签页定时器最坏节流（Chrome 隐藏页约 1 次/分钟）。
HEARTBEAT_STALE_SECONDS = 90

# Windows 控制台 ANSI 颜色（Win10+ 支持）
os.system("")  # 启用 VT 转义序列
_C = {
    "accent": "\033[38;5;99m",
    "ok": "\033[92m",
    "sub": "\033[90m",
    "bad": "\033[91m",
    "bold": "\033[1m",
    "end": "\033[0m",
}


def _c(key, text):
    return f"{_C[key]}{text}{_C['end']}"


# ========== Job Object：主进程死亡时自动杀光所有子进程 ==========
def make_job():
    """创建 kill-on-close 的 Job Object；本进程退出（含窗口被直接关闭）时系统级清理全部子进程"""
    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC_LIMIT_INFO(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class EXT_LIMIT_INFO(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC_LIMIT_INFO),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    k32 = ctypes.windll.kernel32
    job = k32.CreateJobObjectW(None, None)
    info = EXT_LIMIT_INFO()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    return job


def assign_job(job, proc):
    if job:
        ctypes.windll.kernel32.AssignProcessToJobObject(job, int(proc._handle))


def check_env():
    """检查环境（只报关键结论）"""
    checks = [
        (BACKEND_DIR / "app" / "main.py", "后端入口 backend/app/main.py"),
        (FRONTEND_DIR / "package.json", "前端 frontend/package.json"),
        (Path(CONDA_PYTHON), f"conda 环境 {CONDA_PYTHON}"),
    ]
    for path, desc in checks:
        if not path.exists():
            print(_c("bad", f"  [×] 缺少{desc}"))
            sys.exit(1)
    print(_c("ok", "  [✓] 环境检查通过"))


def start_backend():
    """启动后端（仅关键日志：关闭每请求 access log）"""
    cmd = [
        CONDA_PYTHON, "-m", "uvicorn",
        "app.main:app",
        "--reload",
        "--port", str(BACKEND_PORT),
        "--no-access-log",  # 只保留启动横幅与错误，请求日志不刷屏
    ]
    return subprocess.Popen(
        cmd,
        cwd=str(BACKEND_DIR),
        creationflags=subprocess.CREATE_NEW_CONSOLE,  # 新窗口
    )


def start_frontend():
    """启动前端（vite 仅输出警告/错误，请求行不刷屏）"""
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    return subprocess.Popen(
        [npm_cmd, "run", "dev", "--", "--logLevel", "warn"],
        cwd=str(FRONTEND_DIR),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        shell=True,
    )


def start_browser():
    """起独立浏览器实例（独立用户数据目录），返回 Popen；找不到则回退系统默认浏览器并返回 None"""
    for exe in BROWSER_CANDIDATES:
        if Path(exe).exists():
            try:
                shutil.rmtree(BROWSER_PROFILE, ignore_errors=True)
                return subprocess.Popen([
                    exe, "--new-window",
                    f"--user-data-dir={BROWSER_PROFILE}",
                    "--no-first-run", "--no-default-browser-check",
                    APP_URL,
                ])
            except OSError:
                continue
    webbrowser.open(APP_URL)
    return None


def page_idle_seconds(timeout=2.0):
    """查询后端：最近一次前端页面心跳距今的秒数；接口不可达返回 None。

    前端 App 挂载即上报心跳并每 20s 续报（POST /api/v1/meta/heartbeat），
    本函数只读不写（GET），不会刷新心跳时间。
    """
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{BACKEND_PORT}/api/v1/meta/heartbeat", timeout=timeout
        ) as resp:
            return float(json.loads(resp.read()).get("idle_seconds", 1e9))
    except Exception:
        return None


def main():
    job = make_job() if os.name == "nt" else None

    print()
    print(_c("accent", "  ╭──────────────────────────────────────────╮"))
    print(_c("accent", "  │") + _c("bold", "        ResuMatch AI  ·  一键启动          ") + _c("accent", "│"))
    print(_c("accent", "  ╰──────────────────────────────────────────╯"))

    check_env()

    print(_c("sub", "  [1/2] 启动后端窗口..."), end="", flush=True)
    backend_proc = start_backend()
    time.sleep(3)
    print(_c("ok", " 已弹出"))

    print(_c("sub", "  [2/2] 启动前端窗口..."), end="", flush=True)
    frontend_proc = start_frontend()
    print(_c("ok", " 已弹出"))

    assign_job(job, backend_proc)
    assign_job(job, frontend_proc)

    print(_c("sub", "  等待就绪并打开浏览器..."))
    time.sleep(8)
    browser_proc = start_browser()
    if browser_proc:
        assign_job(job, browser_proc)

    print()
    print(_c("ok", "  ✓ 启动完成（服务日志在两个独立窗口，保持安静）"))
    print()
    print(f"    {_c('accent', '页面')}  {APP_URL}")
    print(f"    {_c('accent', '接口')}  http://127.0.0.1:{BACKEND_PORT}")
    print(f"    {_c('accent', '文档')}  http://127.0.0.1:{BACKEND_PORT}/docs")
    print()
    if browser_proc:
        print(_c("sub", "    停止：关闭本窗口，或关闭所有已打开的页面（约 90 秒后服务自动退出）"))
    else:
        print(_c("sub", "    停止：关闭两个服务窗口，或在此处 Ctrl+C"))
    print()

    try:
        if browser_proc:
            browser_proc.wait()  # 阻塞直到浏览器进程退出
            print(_c("sub", "\n  浏览器窗口已关闭"))
            # 浏览器进程退出 ≠ 没人在用：用户可能关掉弹出的窗口后继续用自己的浏览器，
            # 或独立实例把 URL 转发给已有进程后立即退出。心跳仍活跃就继续服务，
            # 彻底无心跳（HEARTBEAT_STALE_SECONDS）才真正关停，避免使用中途被杀。
            unreachable = 0  # 后端 --reload 重启窗口期约 1-2s，连续多次不可达才认定异常
            while True:
                if backend_proc.poll() is not None or frontend_proc.poll() is not None:
                    print(_c("sub", "\n  服务进程已退出，正在收尾..."))
                    break
                idle = page_idle_seconds()
                if idle is None:
                    unreachable += 1
                    if unreachable >= 3:
                        print(_c("sub", "\n  无法确认页面状态，正在停止服务..."))
                        break
                else:
                    unreachable = 0
                    if idle > HEARTBEAT_STALE_SECONDS:
                        print(_c("sub", "\n  页面已全部关闭，正在停止服务..."))
                        break
                time.sleep(5)
        else:
            # 无独立浏览器：任一服务退出即结束
            while True:
                if backend_proc.poll() is not None or frontend_proc.poll() is not None:
                    break
                time.sleep(1)
    except KeyboardInterrupt:
        print(_c("sub", "\n  正在停止服务..."))
    finally:
        for proc in (browser_proc, frontend_proc, backend_proc):
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass
        shutil.rmtree(BROWSER_PROFILE, ignore_errors=True)
        print(_c("ok", "  已退出（全部服务已终止）"))


if __name__ == "__main__":
    main()
