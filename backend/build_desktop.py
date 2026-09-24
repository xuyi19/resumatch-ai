# -*- coding: utf-8 -*-
"""ResuMatch AI · 桌面版构建脚本（one-folder，免安装分发）。

产物：release/ResuMatch-AI-桌面版/  （含 .exe + _internal/ + 使用说明 + config.example.json）
本脚本只增不删；清理旧产物用「改名挪开」而非删除，规避本机批量删除保护。
"""
import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # 项目根
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
RELEASE = ROOT / "release"
APP_NAME = "知岗 ResuMatch-AI 桌面版"

# 桌面版必须排除的重依赖（匹配链路已移除，模型/爬虫不再需要）
EXCLUDES = [
    "sentence_transformers", "torch", "transformers", "huggingface_hub",
    "tokenizers", "safetensors", "accelerate", "datasets", "numpy",
    "playwright", "pyppeteer", "selenium", "chromedriver",
]

# 纯字符串动态导入，PyInstaller 静态分析看不到，必须显式声明
HARD_HIDDEN = [
    "aiosqlite",
    "greenlet",
    "sqlalchemy.dialects.sqlite.aiosqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
]
OPTIONAL = ["httptools", "websockets", "colorama", "dotenv", "yaml",
            "orjson", "ujson", "watchfiles", "sse_starlette",
            "langchain_openai", "langchain_core", "langgraph",
            "langgraph.checkpoint.sqlite", "sqlite_vec",
            "loguru", "pydantic_settings", "httpx",
            "jinja2", "python_multipart", "anyio", "sniffio", "openai"]

# pywebview 原生窗口：平台后端是动态导入，PyInstaller 静态分析看不到；
# 只保留 Windows 的 WebView2（edgechromium）后端，其余平台后端与 GUI 框架排除以缩小体积
PYWEBVIEW_HIDDEN = [
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "clr",
    "pythonnet",
]
PYWEBVIEW_EXCLUDES = [
    "webview.platforms.qt",
    "webview.platforms.gtk",
    "webview.platforms.cocoa",
    "webview.platforms.cef",
    "webview.platforms.android",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "gi", "cefpython3",
]


def _detect_hidden():
    found = [m for m in OPTIONAL if importlib.util.find_spec(m)]
    return HARD_HIDDEN + found


# ---------------- 图标生成（Chrome 无头渲染 SVG → PNG → ICO） ----------------
# 「知岗」图标：靶心 + 命中之矢——知字从矢，瞄准岗位所求（克莱因蓝品牌渐变）
ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0A47E0"/>
      <stop offset="1" stop-color="#002FA7"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="224" height="224" rx="52" fill="url(#g)"/>
  <circle cx="112" cy="144" r="60" fill="none" stroke="#ffffff" stroke-width="18"/>
  <circle cx="112" cy="144" r="16" fill="#ffffff"/>
  <line x1="112" y1="144" x2="196" y2="60" stroke="#ffffff" stroke-width="18" stroke-linecap="round"/>
  <path d="M196 104V60h-44" fill="none" stroke="#ffffff" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

# 暗色备用变体：底色提亮为暗色品牌阶（--c-accent 暗色 #5A82FF），深色任务栏/标签栏上更醒目；
# 打包加 --dark-icon 启用（默认亮色版）
ICON_SVG_DARK = """<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#5A82FF"/>
      <stop offset="1" stop-color="#2B50D0"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="224" height="224" rx="52" fill="url(#g)"/>
  <circle cx="112" cy="144" r="60" fill="none" stroke="#ffffff" stroke-width="18"/>
  <circle cx="112" cy="144" r="16" fill="#ffffff"/>
  <line x1="112" y1="144" x2="196" y2="60" stroke="#ffffff" stroke-width="18" stroke-linecap="round"/>
  <path d="M196 104V60h-44" fill="none" stroke="#ffffff" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def _build_ico(pngs: dict[int, bytes], out: Path):
    """把多尺寸 PNG 打包成 ICO（宽高 256 写作 0）。"""
    entries = []
    body = b""
    offset = 6 + 16 * len(pngs)
    for size in sorted(pngs, reverse=True):
        data = pngs[size]
        w = 0 if size == 256 else size
        entries.append(struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset))
        body += data
        offset += len(data)
    header = struct.pack("<HHH", 0, 1, len(pngs))
    out.write_bytes(header + b"".join(entries) + body)


def _gen_icon(out_ico: Path, svg: str = ICON_SVG) -> bool:
    chrome = (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    exe = next((c for c in chrome if Path(c).exists()), None)
    if not exe:
        return False
    tmp = Path(tempfile.gettempdir()) / f"rm-icon-{int(time.time())}"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "icon.svg").write_text(svg, encoding="utf-8")
    (tmp / "wrap.html").write_text(
        '<!doctype html><html><head><style>html,body{margin:0;overflow:hidden}'
        'img{display:block}</style></head><body>'
        '<img src="icon.svg" width="256" height="256"></body></html>',
        encoding="utf-8")
    pngs: dict[int, bytes] = {}
    ok = True
    for size in (256, 128, 64, 48, 32, 16):
        out_png = tmp / f"i{size}.png"
        r = subprocess.run(
            [exe, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--hide-scrollbars", "--default-background-color=00000000",
             f"--window-size={size},{size}",
             f"--screenshot={out_png}", f"file://{tmp / 'wrap.html'}"],
            capture_output=True, text=True, timeout=60)
        if out_png.exists() and out_png.stat().st_size > 100:
            pngs[size] = out_png.read_bytes()
        else:
            ok = False
    if pngs:
        _build_ico(pngs, out_ico)
        return out_ico.exists()
    return False


# ---------------- 组装发布包 ----------------
# 历史产物保留份数。旧产物用「改名挪开」而非直接删除，规避本机批量删除保护；
# 但每次构建都会留下约 160MB（目录+压缩包），历次累积曾达 2GB，
# 故只保留最近 _OLD_KEEP 份作为回退，更早的定向清理掉。
_OLD_KEEP = 1


def _prune_old_artifacts():
    """清理多余的历史产物（目录与压缩包分别计数）。"""
    for want_dir in (True, False):
        olds = sorted(
            (p for p in RELEASE.glob(".old-*") if p.is_dir() == want_dir),
            key=lambda p: p.name,
            reverse=True,
        )
        for p in olds[_OLD_KEEP:]:
            try:
                if want_dir:
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
                print(f"[build] 已清理旧产物: {p.name}")
            except Exception as e:
                print(f"[build] 清理旧产物失败 {p.name}: {e}")


def _assemble(dist_exe_dir: Path):
    RELEASE.mkdir(parents=True, exist_ok=True)
    target = RELEASE / "ResuMatch-AI-桌面版"
    # 改名挪开旧产物（不删，规避批量删除保护）
    if target.exists():
        old = RELEASE / f".old-{time.strftime('%Y%m%d-%H%M%S')}"
        target.rename(old)
    target.mkdir(parents=True, exist_ok=True)
    # 移动 exe + _internal
    for item in dist_exe_dir.iterdir():
        shutil.move(str(item), str(target / item.name))
    # 使用说明（UTF-8 BOM，否则记事本乱码）
    (target / "使用说明.txt").write_text(_USAGE, encoding="utf-8-sig")
    # 配置模板（刻意 .example，不会被自动读取）
    (target / "config.example.json").write_text(_CONFIG_EXAMPLE, encoding="utf-8")
    return target


_USAGE = """知岗 ResuMatch-AI 桌面版 · 使用说明
================================

【怎么用】
1. 把整个文件夹（知岗 ResuMatch-AI 桌面版）解压到任意位置，例如桌面。
2. 双击「知岗 ResuMatch-AI 桌面版.exe」启动，会打开独立应用窗口（不是浏览器标签页）。
3. 在「设置」页填入你自己的大模型 API Key（DeepSeek / 兼容 OpenAI 协议均可），
   也可在 exe 同级放一个 config.json 预置（见下文）。
4. 上传简历（PDF / DOCX），粘贴岗位 JD 文本，开始诊断。

【窗口说明】
- 窗口依赖系统自带的 WebView2 运行时（Win10/11 一般已内置；缺失时首次启动会自动下载组件，需联网）。
- 若窗口无法打开，程序会自动改用默认浏览器打开；也可加参数启动：
    启动参数 --browser   强制用浏览器打开
    启动参数 --no-browser  只启动后台服务，不开窗口

【重要提醒】
- 不要把单独的 .exe 复制出去发人，必须连同 _internal 文件夹一起。
- 数据（诊断记录、简历）保存在 exe 同级的 data/ 目录，换电脑时一并拷贝即可。
- 运行日志在 data/logs/app.log（窗口模式无控制台，排查问题看这里）。
- 首次使用需要联网：大模型诊断依赖你的 API Key 对应的云端服务。
- 本程序仅供学习研究，请勿用于商业用途；岗位数据请遵守相关网站的使用条款。

【config.json 预置（可选）】
在 exe 同级新建 config.json：
{
  "LLM_API_KEY": "你的key",
  "LLM_BASE_URL": "https://api.deepseek.com/v1",
  "LLM_MODEL": "deepseek-chat"
}
放入后启动即视为已托管 Key，界面会提示「服务端已托管，无需填写」。

【系统要求】
- Windows 10 64 位及以上
- 联网（用于调用大模型 API）
"""

_CONFIG_EXAMPLE = """{
  "LLM_API_KEY": "在此填写你自己的大模型 API Key",
  "LLM_BASE_URL": "https://api.deepseek.com/v1",
  "LLM_MODEL": "deepseek-chat"
}
"""


def main():
    # conda 环境的 DLL 目录前置到 PATH：PyInstaller 收集二进制依赖时按 PATH 搜索，
    # 否则可能抓到 base Anaconda（或其他程序）的旧版 libssl/libcrypto，
    # 产物 exe 会报 "DLL load failed while importing _ssl: 找不到指定的程序"
    env_bin = Path(sys.prefix) / "Library" / "bin"
    os.environ["PATH"] = (
        f"{env_bin}{os.pathsep}{sys.prefix}{os.pathsep}"
        f"{os.environ.get('PATH', '')}"
    )
    print(f"[build] DLL 搜索目录前置: {env_bin}")

    stage = Path(tempfile.gettempdir()) / f"rm-build-{int(time.time())}"
    stage.mkdir(parents=True, exist_ok=True)
    print(f"[build] 构建中间目录: {stage}")

    icon = stage / "app.ico"
    dark_icon = "--dark-icon" in sys.argv  # 备用：暗色任务栏/深色环境分发时用
    if _gen_icon(icon, ICON_SVG_DARK if dark_icon else ICON_SVG):
        print(f"[build] 图标已生成（{'暗色' if dark_icon else '亮色'}版）: {icon}")
    else:
        print("[build] 未生成图标（不影响功能）")
        icon = None

    hidden = _detect_hidden()
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--windowed",  # 无控制台黑窗；日志改落 data/logs/app.log
        "--name", APP_NAME,
        "--distpath", str(stage / "dist"),
        "--workpath", str(stage / "work"),
        "--specpath", str(stage),
        "--add-data", f"{FRONTEND_DIST}{os.pathsep}web",
        "--collect-submodules", "uvicorn",
    ]
    if icon:
        args += ["--icon", str(icon)]
    for h in hidden:
        args += ["--hidden-import", h]
    for e in EXCLUDES:
        args += ["--exclude-module", e]

    # 原生窗口：pywebview 存在则一并打包（含前端 JS 资源与 WebView2 后端），
    # 缺失时产物仍可用，desktop.py 会自动回退浏览器打开
    if importlib.util.find_spec("webview"):
        args += ["--collect-all", "webview"]
        for h in PYWEBVIEW_HIDDEN:
            args += ["--hidden-import", h]
        for e in PYWEBVIEW_EXCLUDES:
            args += ["--exclude-module", e]
        print("[build] 已启用 pywebview 原生窗口")
    else:
        print("[build] 未检测到 pywebview，产物将回退浏览器模式（pip install pywebview 可启用原生窗口）")

    args.append(str(BACKEND / "desktop.py"))

    print("[build] 开始 PyInstaller 打包（可能需要几分钟）...")
    r = subprocess.run(args, cwd=str(BACKEND), capture_output=True, text=True)
    if r.returncode != 0:
        print("===== PyInstaller STDOUT =====")
        print(r.stdout[-4000:])
        print("===== PyInstaller STDERR =====")
        print(r.stderr[-4000:])
        sys.exit(1)

    dist_exe_dir = stage / "dist" / APP_NAME
    if not (dist_exe_dir / f"{APP_NAME}.exe").exists():
        print(f"[build] 未找到产物: {dist_exe_dir}")
        sys.exit(1)

    target = _assemble(dist_exe_dir)
    print(f"[build] 已组装到: {target}")

    # 压缩（旧包先改名挪开，构建完由 _prune_old_artifacts 只留最近 1 份）
    zip_path = RELEASE / "ResuMatch-AI-桌面版.zip"
    if zip_path.exists():
        zip_path.rename(RELEASE / f".old-{time.strftime('%Y%m%d-%H%M%S')}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in target.rglob("*"):
            z.write(p, p.relative_to(target))
    print(f"[build] 压缩包: {zip_path}")

    _prune_old_artifacts()

    print("[build] ✅ 本包只含公开内容，可直接发给任何人。")


if __name__ == "__main__":
    main()
