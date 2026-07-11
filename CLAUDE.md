# CLAUDE.md — profile-readme

GitHub **profile README** 仓库：`github.com/jackiectl/jackiectl`
（⚠ 仓库名必须与用户名**完全相同**，`README.md` 才会显示在 profile 页顶部。别改名。）

父目录 `personal_website/CLAUDE.md` 和全局 `~/.claude/CLAUDE.md` 会自动叠加，这里不重复。

---

## 1. 最重要的一条：README.md 是**生成物**，不要手改

```
data/profile.json   ← 唯一可编辑的内容源（PROFILE.md 的机读投影）
       ↓  python3 build.py
README.md           ← 生成物。手改会被下次 build 覆盖
```

- **加一个项目 / 一条 timeline** = 往 `data/profile.json` 加一条 → `python3 build.py`。
  **不改 `build.py`，不改 README。** 这就是铁律 B 在本仓库的落地。
- `python3 build.py --check` → README 与 JSON 不一致时 exit 1（可做 CI）。
- 事实源仍是 `../PROFILE.md`。**先改 PROFILE.md，再把改动镜像进 `profile.json`。**

## 2. 卡片服务：能用的 / 已死的（2026-07-11 实测）

**每次加新卡片前先 `curl` 验，200 也要看 SVG 内容** —— 这些免费 Vercel 实例说停就停。

| 服务 | 状态 |
|---|---|
| `github-stats-extended.vercel.app` (MIT) | ✅ 用中。stats 卡片 |
| `streak-stats.demolab.com` | ✅ 用中。连续贡献 |
| `github-readme-activity-graph.vercel.app` | ✅ 用中。贡献曲线 |
| `komarev.com/ghpvc` | ✅ 用中。Profile views |
| `img.shields.io` | ✅ 用中。徽章 |
| **`github-readme-stats.vercel.app`**（网上最常推荐的那个） | ❌ **`DEPLOYMENT_PAUSED`** |
| **`github-profile-trophy.vercel.app`** | ❌ **`402 DEPLOYMENT_DISABLED`** |

**`top-langs` 卡片故意没放** —— 现在三个仓库都是空的，渲染出来是张只有标题的空卡。
等 `site-2d` / `site-3d` 推上去、有语言统计了再加（往 `profile.json` 的 `cards` 里加一条即可）。

### light / dark 双主题

GitHub README 会剥掉 `<style>` 和 class，所以 `prefers-color-scheme` 只能靠
`<picture>` + `<source media=...>` 这个结构化钩子实现（`build.py: themed_card()`）。
**不能只挂一张深色卡** —— 一半读者是 light mode，深色卡在白底上是黑底一块。

用 `gruvbox` / `gruvbox_light`（暖色，呼应点心主题）。已验证 light 主题的正文
fill 是 `#427b58`（深绿）不是浅灰，白底上读得清。

## 3. 没放 GitHub Actions 的原因

本可以加个 workflow 自动跑 `build.py --check` 防漂移。**故意没加**：
fine-grained PAT 若没有 `workflows` 权限，**push 含 `.github/workflows/` 的 commit 会被 GitHub 直接拒绝**，
反而把首推搞挂。要加的话，先去 PAT 设置里给这个仓库开 Workflows 权限。

## 4. 状态 / 待办

- ✅ Skills 里的 `ML & Data`（PyTorch / scikit-learn / Gaussian Processes / Foundation-Model
  Fine-Tuning / HDF5）和 `Slurm / HPC` **已由用户确认属实**（2026-07-11）。
  🔴 **但 `cv/` 里还没补** —— 见 `PROFILE.md` §6 的红字。
- ⬜ push 之后去 profile 页**肉眼确认三张卡片都出图**（服务挂掉时 GitHub 显示破图）。
- Publications 现在是 "In preparation."（铁律 B ④ 要求板块常驻）。有论文了往
  `profile.json` 的 `publications: []` 里加，板块自动从 "In preparation" 切成真条目 —— 已实测。
