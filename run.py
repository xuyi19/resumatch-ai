"""
ResuMatch AI 一键启动脚本
使用方法：python run.py
"""
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# ========== 配置 ==========
ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

# ★ 你的 conda 环境里 python 和 uvicorn 的绝对路径
# 如果路径不对，执行 `where python` 和 `where uvicorn` 查到实际路径
CONDA_PYTHON = r"C:\Users\许\.conda\envs\resumatch-ai\python.exe"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173


def check_env():
    """检查环境"""
    if not (BACKEND_DIR / "app" / "main.py").exists():
        print("[×] 找不到 backend/app/main.py")
        sys.exit(1)
    if not (FRONTEND_DIR / "package.json").exists():
        print("[×] 找不到 frontend/package.json")
        sys.exit(1)
    if not Path(CONDA_PYTHON).exists():
        print(f"[×] 找不到 conda python: {CONDA_PYTHON}")
        print("    请用 `where python` 查到实际路径后修改 CONDA_PYTHON")
        sys.exit(1)
    print("[✓] 环境检查通过")


def start_backend():
    """启动后端"""
    print(f"\n[1/3] 启动后端 (port {BACKEND_PORT})...")
    cmd = [
        CONDA_PYTHON, "-m", "uvicorn",
        "app.main:app",
        "--reload",
        "--port", str(BACKEND_PORT),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(BACKEND_DIR),
        creationflags=subprocess.CREATE_NEW_CONSOLE,  # 新窗口
    )
    return proc


def start_frontend():
    """启动前端"""
    print(f"[2/3] 启动前端 (port {FRONTEND_PORT})...")
    # Windows 上 npm 是 npm.cmd
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    cmd = [npm_cmd, "run", "dev"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(FRONTEND_DIR),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        shell=True,
    )
    return proc


def open_browser():
    """打开浏览器"""
    print(f"[3/3] 打开浏览器...")
    time.sleep(8)  # 等前端就绪
    webbrowser.open(f"http://localhost:{FRONTEND_PORT}")


def main():
    print("=" * 50)
    print("  ResuMatch AI 一键启动")
    print("=" * 50)

    check_env()

    print("\n⚠️  请确认 phpStudy 的 MySQL 已启动！\n")

    backend_proc = start_backend()
    time.sleep(3)
    frontend_proc = start_frontend()
    open_browser()

    print("\n" + "=" * 50)
    print("  ✓ 全部启动完成")
    print("=" * 50)
    print(f"  前端:  http://localhost:{FRONTEND_PORT}")
    print(f"  后端:  http://127.0.0.1:{BACKEND_PORT}")
    print(f"  文档:  http://127.0.0.1:{BACKEND_PORT}/docs")
    print()
    print("  两个服务在独立窗口运行")
    print("  关闭对应窗口可停止服务")
    print("=" * 50)

    # 询问是否启动内网穿透
    answer = input("\n是否启动内网穿透？(y/n): ").strip().lower()
    if answer == "y":
        try:
            subprocess.Popen(
                ["cpolar", "http", str(FRONTEND_PORT)],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                shell=True,
            )
            print("✓ cpolar 已启动，查看新窗口获取公网地址")
        except FileNotFoundError:
            print("× 找不到 cpolar 命令，请确认已安装并配置 PATH")

    input("\n按 Enter 退出...")

    # 等待两个子进程结束
    backend_proc.wait()
    frontend_proc.wait()


if __name__ == "__main__":
    main()
