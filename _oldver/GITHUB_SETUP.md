# GitHub 建库 & 自动发版流程（CatClock）

> 目标：让挂件里的「检查更新」真正生效 —— 推送 tag 后 GitHub Actions 自动打包 exe 并发 Release。
> 全程只需做一次，之后发版一条命令。

---

## 0. 已经就绪的部分（不用再做）

| 项目 | 状态 |
|---|---|
| `git remote origin` | 已指向 `git@github.com:Xingsenya/CatClock.git` |
| 版本号 | `catclock/__init__.py` → `__version__ = "1.1.0"` |
| 更新检查 | `catclock/update.py` → 查 `api.github.com/repos/Xingsenya/CatClock/releases/latest` |
| CI 流水线 | `.github/workflows/release.yml`（tag `v*` 触发打包 + 发 Release） |
| 发布脚本 | `tools/publish.py`（提交 → 推 main → 打 tag） |
| 冒烟脚本 | `tools/smoke.py` / `tools/smoke.py --exe` |

**缺的只有：GitHub 上那个仓库本身。** 下面的步骤就是补这一步。

---

## 1. 创建仓库（GitHub 网页，30 秒）

1. 打开 <https://github.com/new>
2. **Repository name**：`CatClock`（大小写不敏感，但必须叫这个，remote 已按它配好）
3. **Visibility**：选 **Public**
   - ⚠️ 必须公开：`update.py` 是匿名请求，私有仓库查不到 Release，自动更新会失效
4. **不要**勾选 "Add a README file" / ".gitignore" / "License"（本地已有，勾了会冲突）
5. 点 **Create repository**

建好后页面会显示一个空仓库的提示界面，保持打开，下一步要用。

---

## 2. 配置 SSH 认证（二选一）

### 方案 A：SSH key（推荐，一次配置永久免密）

**2-1 复制公钥**（在你自己的 PowerShell 里跑，别用被 ACL 挡住的会话）：

```powershell
type $env:USERPROFILE\.ssh\catclock-deploy.pub | clip
```

> 如果提示文件不存在，先生成一把：
> ```powershell
> ssh-keygen -t ed25519 -C "catclock" -f "$env:USERPROFILE\.ssh\catclock-deploy"
> ```

> **`Load key ...: Permission denied` 怎么办**
> 本机 `C:\Users\qizhuo\.ssh` 被 ACL 挡住时，脚本读不到私钥。解决办法是在仓库内再放一份：
> ```powershell
> ssh-keygen -t ed25519 -C "catclock" -f "D:\CatClock\.git\catclock-deploy"
> type D:\CatClock\.git\catclock-deploy.pub | clip
> ```
> 把这段新公钥也加到 GitHub（Deploy keys 允许多个）。`tools/publish.py` 会**优先**用 `.git/catclock-deploy`，之后推送即可全自动。
**2-2 添加到 GitHub**（加在**账号**上，一次生效所有仓库）：

GitHub 右上角头像 → **Settings** → 左侧 **SSH and GPG keys** → **New SSH key**
- Title：`CatClock-PC`
- Key type：`Authentication Key`
- Key：粘贴（Ctrl+V）
- → **Add SSH key**

**2-3 验证连通**：

```powershell
ssh -T git@github.com
```

看到 `Hi Xingsenya! You've successfully authenticated...` 即成功。

> 若报 `hostkeys_foreach failed ... Permission denied`（Windows ACL 挡住 known_hosts），先跑：
> ```powershell
> $env:GIT_SSH_COMMAND = "ssh -o UserKnownHostsFile=D:\CatClock\.git\gh_known_hosts -o StrictHostKeyChecking=no"
> ```
> `tools/publish.py` 已内置这个绕过，正常情况不用管。

### 方案 B：HTTPS（不想配 key 时用）

```powershell
cd D:\CatClock
git remote set-url origin https://github.com/Xingsenya/CatClock.git
```

首次推送会弹浏览器登录 GitHub，之后由 Git Credential Manager 记住。

---

## 3. 首次推送 + 发第一个 Release

```powershell
cd D:\CatClock
python tools/smoke.py --exe        # 可选：先本地冒烟（编译 + 预览 + exe 跑 15 秒）
python tools/publish.py            # 提交 → 推 main → 打 v1.1.0 tag → 推送 tag
```

脚本会输出 Release 页和 Actions 页地址。

---

## 4. 等待 CI 出包

打开 <https://github.com/Xingsenya/CatClock/actions>

- 看到 `Build & Release` 工作流运行 → 约 2–4 分钟
- 绿勾后去 <https://github.com/Xingsenya/CatClock/releases>
- 应出现 `v1.1.0`，附件 `CatClock-v1.1.0.exe`

---

## 5. 验证自动更新

1. 启动 `dist\CatClock.exe`
2. 右键 → **检查更新**（或等启动自检）
3. 把 `__version__` 改成 `1.1.1` 再发一次 tag，旧版挂件应能提示新版本

---

## 日常发版流程（以后每次）

```powershell
# 1. 改版本号
#    catclock/__init__.py → __version__ = "1.2.0"

# 2. 本地验证
python tools/smoke.py --exe

# 3. 一键发布
python tools/publish.py -m "v1.2.0 说明"
```

`publish.py` 会自动：提交全部改动 → 推 `main` → 按 `__version__` 打 `vX.Y.Z` tag → 推送 tag → CI 打包发 Release。

---

## 排障表

| 现象 | 原因 | 处理 |
|---|---|---|
| `repository not found` | 仓库没建 / 名字不对 / key 没权限 | 确认第 1、2 步 |
| `Permission denied (publickey)` | key 未添加，或私钥读不到 | 重做第 2 步；或改走 HTTPS 方案 B |
| `Host key verification failed` | known_hosts 被 ACL 挡 | 用第 2 步的 `GIT_SSH_COMMAND`；`publish.py` 已内置 |
| `tag already exists` | `__version__` 没改 | 改版本号；或 `git tag -d v1.1.0 && git push origin :refs/tags/v1.1.0` |
| Actions 红叉 | 依赖或路径问题 | 点进 Actions 日志看具体步骤；常见是 Python 版本，workflow 里已锁 3.11 |
| Release 生成但没附件 | 打包失败或 exe 路径变了 | 检查 `CatClock.spec` 的 `name='CatClock'` |
| 挂件提示"已是最新"但 Release 有新版 | tag 与 `__version__` 相同 | `_vtuple` 比较相等不算新版，必须 bump 版本号 |

---

## 换机器同步

```powershell
git clone git@github.com:Xingsenya/CatClock.git
cd CatClock
pip install PyQt6 pyinstaller
python cat_clock.py
```

配置（含自定义语录）不走 git：用 设置 → 高级 → **导出配置 / 导入配置** 迁移。
