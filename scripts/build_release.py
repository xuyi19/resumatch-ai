# -*- coding: utf-8 -*-
"""知岗 ResuMatch-AI · 发布流程自动化（M48）。

一条命令完成发版全链路：
  1. 版本号自增（backend/app/__init__.py 为单一事实源；patch 默认，--minor 可选）
  2. 同步 frontend/package.json 与根目录 VERSION（exe 更新检查用）
  3. ChangelogView.vue 站内更新日志自动生成新条目（取 git 提交记录，旧条目 current 摘除）
  4. pytest 全量 + npm build 验证（--skip-tests 可跳过）
  5. build_desktop.py 打包（release/ 组装 + 压缩 + 旧产物改名挪开）
  6. release/ 清理校验（旧产物只保留 1 份、产物文件齐全）
  7. git 提交 + 打 tag + 推送（gitee 必推，github 尽力而为）

用法（resumatch-ai conda 环境、项目根目录下运行）:
  python scripts/build_release.py --title "本次发布主题" [--minor] [--from <ref>]
      [--skip-tests] [--dry-run] [--yes]

失败回退：脚本只改动 4 个文件（__init__.py / package.json / VERSION / ChangelogView.vue），
`git checkout -- <文件>` 即可还原；tag 未推远端时可 `git tag -d` 删除。
"""
import argparse
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT_PY = ROOT / "backend" / "app" / "__init__.py"
PKG_JSON = ROOT / "frontend" / "package.json"
VERSION_FILE = ROOT / "VERSION"
CHANGELOG_VUE = ROOT / "frontend" / "src" / "views" / "ChangelogView.vue"
BUILD_DESKTOP = ROOT / "backend" / "build_desktop.py"
RELEASE = ROOT / "release"

MAX_ITEMS = 12  # 站内日志单条目最多行数，防刷屏


def run(cmd, cwd=ROOT, check=True, timeout=3600):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    if check and r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        raise SystemExit(f"[release] 命令失败（exit {r.returncode}）: {cmd[0]}")
    return r


def pick_python() -> str:
    """优先 resumatch-ai conda 环境的 python（跑 pytest 必须用它）。"""
    if "resumatch-ai" in sys.executable:
        return sys.executable
    fallback = Path(r"E:\conda\envs\resumatch-ai\python.exe")
    if fallback.exists():
        print(f"[release] 当前解释器非 resumatch-ai 环境，pytest 改用: {fallback}")
        return str(fallback)
    return sys.executable


# ---------------- 版本号 ----------------

def read_version() -> str:
    m = re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', INIT_PY.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("[release] 未在 app/__init__.py 找到 __version__")
    return m.group(1)


def bump(version: str, minor: bool) -> str:
    a, b, c = (int(x) for x in version.split("."))
    return f"{a}.{b + 1}.0" if minor else f"{a}.{b}.{c + 1}"


def apply_version(new_version: str):
    text = INIT_PY.read_text(encoding="utf-8")
    INIT_PY.write_text(re.sub(r'__version__\s*=\s*"[\d.]+"',
                              f'__version__ = "{new_version}"', text), encoding="utf-8")
    pkg = PKG_JSON.read_text(encoding="utf-8")
    PKG_JSON.write_text(re.sub(r'"version"\s*:\s*"[\d.]+"',
                               f'"version": "{new_version}"', pkg, count=1), encoding="utf-8")
    VERSION_FILE.write_text(new_version + "\n", encoding="utf-8")
    print(f"[release] 版本号已同步: {INIT_PY.name} / package.json / VERSION")


# ---------------- 站内更新日志 ----------------

def git_subjects(since: str | None) -> list[str]:
    if since:
        r = run(["git", "log", "--pretty=%s", f"{since}..HEAD"], check=False)
        if r.returncode != 0:
            raise SystemExit(f"[release] --from {since} 不是有效引用")
    else:
        r = run(["git", "log", "--pretty=%s", "-10"])
    subs = [s.strip() for s in r.stdout.splitlines() if s.strip()]
    subs = [re.sub(r"^(feat|fix|docs|style|refactor|perf|test|chore|hotfix)(\([^)]*\))?:\s*", "", s)
            for s in subs]
    return subs[:MAX_ITEMS]


def guess_type(subject: str) -> str:
    if re.search(r"修复|修正|hotfix|fix", subject, re.I):
        return "修复"
    if re.search(r"优化|重构|精简|收紧|perf|refactor", subject, re.I):
        return "优化"
    if re.search(r"^docs|文档|chore|test|测试", subject, re.I):
        return "变更"
    return "新增"


def build_entry(version: str, date: str, title: str, subjects: list[str]) -> str:
    lines = [f"  {{", f"    version: 'v{version}',", f"    date: '{date}',",
             f"    title: '{title}',", f"    current: true,", "    items: ["]
    lines += [f"      {{ type: '{guess_type(s)}', text: '{s}' }}," for s in subjects]
    lines += ["    ],", "  },"]
    return "\n".join(lines)


def apply_changelog(entry: str):
    text = CHANGELOG_VUE.read_text(encoding="utf-8")
    if "current: true" not in text:
        raise SystemExit("[release] ChangelogView.vue 中未找到 current 标记，中止防误改")
    # 文件中第一个 current: true 属于当前最新条目，摘除后由新条目顶替
    text = text.replace("current: true,", "current: false,", 1)
    marker = "const logs = ["
    idx = text.index(marker) + len(marker)
    CHANGELOG_VUE.write_text(text[:idx] + "\n" + entry + "\n" + text[idx:], encoding="utf-8")
    print(f"[release] 站内更新日志已插入新条目: {CHANGELOG_VUE.name}")


# ---------------- 主流程 ----------------

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="知岗 ResuMatch-AI 发布自动化")
    ap.add_argument("--title", required=True, help="站内更新日志的条目标题")
    ap.add_argument("--minor", action="store_true", help="升 minor（x.Y.0），默认升 patch（x.y.Z）")
    ap.add_argument("--from", dest="since", default=None,
                    help="更新日志取该引用之后的提交（默认：最近一个 tag，无 tag 则取最近 10 条）")
    ap.add_argument("--skip-tests", action="store_true", help="跳过 pytest / npm build 验证（不推荐）")
    ap.add_argument("--dry-run", action="store_true", help="只演练：显示将做的一切，不写盘不打包不推送")
    ap.add_argument("--yes", action="store_true", help="跳过交互确认")
    args = ap.parse_args()

    old_version = read_version()
    new_version = bump(old_version, args.minor)
    tag = f"v{new_version}"
    date = datetime.date.today().isoformat()

    print(f"[release] ===== 演练模式（不产生任何变更）=====" if args.dry_run
          else f"[release] ===== 发版 {tag}（{date}）=====")

    # 0) 预检：工作树干净 + tag 不存在
    st = run(["git", "status", "--porcelain"]).stdout
    dirty = [l for l in st.splitlines() if l.strip() and not l.startswith("??")]
    if dirty:
        raise SystemExit("[release] 工作树有未提交改动，请先提交：\n  " + "\n  ".join(dirty))
    if run(["git", "rev-parse", "-q", "--verify", tag], check=False).returncode == 0:
        raise SystemExit(f"[release] tag {tag} 已存在")
    branch = run(["git", "branch", "--show-current"]).stdout.strip()
    print(f"[release] 预检通过：分支 {branch}，{old_version} → {new_version}")

    # 1) 更新日志内容（提交记录驱动）
    subjects = git_subjects(args.since)
    if not subjects:
        raise SystemExit("[release] 选定范围内没有提交，无法生成更新日志")
    entry = build_entry(new_version, date, args.title, subjects)
    print("[release] 将插入的更新日志条目:\n" + entry)

    if args.dry_run:
        print(f"[release] 后续将执行: pytest → npm build → build_desktop → "
              f"git add 4 文件 → commit → tag {tag} → push gitee/github")
        print("[release] ✅ 演练结束")
        return
    if not args.yes:
        if input(f"[release] 确认发版 {tag}? [y/N] ").strip().lower() != "y":
            raise SystemExit("[release] 已取消")

    # 2) 版本号三处同步 + 日志插入
    apply_version(new_version)
    apply_changelog(entry)

    # 3) 验证
    if not args.skip_tests:
        print("[release] pytest 全量验证...")
        run([pick_python(), "-m", "pytest", "backend/tests", "-q"], timeout=1200)
        print("[release] npm build 验证...")
        npm = shutil.which("npm")
        if not npm:
            raise SystemExit("[release] 未找到 npm")
        run([npm, "run", "build", "--prefix", str(ROOT / "frontend")], timeout=1200)

    # 4) 打包（build_desktop 自带：组装 + 压缩 + 旧产物改名挪开 + 只留 1 份旧产物）
    print("[release] PyInstaller 打包（可能需要几分钟）...")
    run([sys.executable, str(BUILD_DESKTOP)], timeout=3600)

    # 5) release/ 清理校验
    exe = RELEASE / "ResuMatch-AI-桌面版" / "知岗 ResuMatch-AI 桌面版.exe"
    zipped = RELEASE / "ResuMatch-AI-桌面版.zip"
    olds_dir = [p for p in RELEASE.glob(".old-*") if p.is_dir()]
    olds_zip = [p for p in RELEASE.glob(".old-*") if p.is_file()]
    assert exe.exists(), "产物 exe 缺失"
    assert zipped.exists(), "产物 zip 缺失"
    assert len(olds_dir) <= 1 and len(olds_zip) <= 1, "旧产物未按约定只保留 1 份"
    mb = lambda p: f"{p.stat().st_size / 1048576:.0f}MB"
    print(f"[release] 清理校验通过：exe={mb(exe)} zip={mb(zipped)} "
          f"旧目录残留={len(olds_dir)} 旧压缩包残留={len(olds_zip)}")

    # 6) 提交 + tag + 推送
    run(["git", "add", "backend/app/__init__.py", "frontend/package.json",
         "VERSION", "frontend/src/views/ChangelogView.vue"])
    run(["git", "commit", "-m", f"chore: 发版 {tag} —— {args.title}",
         "-m", f"版本号 {old_version}→{new_version}（三处同步）+ 站内更新日志自动生成"])
    run(["git", "tag", tag])
    print(f"[release] 已提交并打 tag {tag}")

    print("[release] 推送 gitee...")
    run(["git", "push", "gitee", branch])
    run(["git", "push", "gitee", tag])
    print("[release] 推送 github（尽力而为）...")
    r = run(["git", "push", "github", branch], check=False)
    if r.returncode == 0:
        run(["git", "push", "github", tag], check=False)
    else:
        print("[release] github 推送失败（网络常态），稍后可手动补推")

    print(f"[release] ✅ {tag} 发布完成")


if __name__ == "__main__":
    main()
