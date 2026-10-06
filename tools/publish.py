# -*- coding: utf-8 -*-
"""一键发布：提交 → 推 main → 按 __version__ 打 tag → 触发 GitHub Actions 发 Release。

用法：
    python tools/publish.py              # 提交全部改动并打当前版本 tag
    python tools/publish.py -m "消息"     # 自定义提交消息
    python tools/publish.py --no-commit  # 不提交，只推 + 打 tag

前置条件（只需做一次）：
    1. GitHub 上创建仓库 Xingsenya/CatClock（Public）
    2. 把 C:\\Users\\qizhuo\\.ssh\\catclock-deploy.pub 加为该仓库的 Deploy key（勾选 Allow write access）
    3. git remote add origin git@github.com:Xingsenya/CatClock.git（已配好）
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT = os.path.join(ROOT, "catclock", "__init__.py")


def run(cmd, check=True):
    print("$ %s" % " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if out.strip():
        print(out.rstrip())
    if check and r.returncode != 0:
        sys.exit(r.returncode)
    return r


def version():
    with open(INIT, "r", encoding="utf-8") as f:
        m = re.search(r'__version__\s*=\s*"([^"]+)"', f.read())
    if not m:
        sys.exit("无法从 catclock/__init__.py 解析 __version__")
    return m.group(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--message", default="")
    ap.add_argument("--no-commit", action="store_true")
    a = ap.parse_args()

    ver = version()
    tag = "v" + ver

    remotes = run(["git", "remote", "-v"]).stdout or ""
    if "origin" not in remotes:
        sys.exit("未配置 origin，先执行：git remote add origin git@github.com:Xingsenya/CatClock.git")

    branch = (run(["git", "branch", "--show-current"]).stdout or "main").strip() or "main"

    if not a.no_commit:
        run(["git", "add", "-A"])
        dirty = run(["git", "diff", "--cached", "--name-only"]).stdout.strip()
        if dirty:
            msg = a.message or ("release %s" % tag)
            run(["git", "commit", "-m", msg])
        else:
            print("(没有待提交的改动)")

    print("推送分支 %s ..." % branch)
    r = run(["git", "push", "-u", "origin", branch], check=False)
    if r.returncode != 0:
        print("\n推送失败。常见原因：")
        print("  1. GitHub 上还没有 Xingsenya/CatClock 仓库 → 先去 github.com/new 创建（Public）")
        print("  2. Deploy key 未添加或未勾选 write → 仓库 Settings → Deploy keys → 添加 catclock-deploy.pub")
        print("  3. 本机私钥读不到（C 盘 ACL）→ 用你自己的终端/PowerShell 跑本脚本")
        sys.exit(r.returncode)

    exist = run(["git", "tag", "-l", tag]).stdout.strip()
    if exist:
        print("tag %s 已存在，跳过打 tag（改版本请修改 catclock/__init__.py 的 __version__）" % tag)
    else:
        run(["git", "tag", "-a", tag, "-m", "CatClock %s" % tag])
        run(["git", "push", "origin", tag])
        print("\ntag %s 已推送，GitHub Actions 开始打包…" % tag)
        print("Release 页面：https://github.com/Xingsenya/CatClock/releases")
        print("Actions 进度：https://github.com/Xingsenya/CatClock/actions")


if __name__ == "__main__":
    main()
