# CLAUDE.md — profile-readme

GitHub **profile README** 仓库：`github.com/jackiectl/jackiectl`
（⚠ 仓库名必须与用户名**完全相同**，`README.md` 才会显示在 profile 页顶部。别改名。）

父目录 `personal_website/CLAUDE.md` 和全局 `~/.claude/CLAUDE.md` 会自动叠加，这里不重复。

---

## 0. 🔴 踩过的坑：README 在仓库页正常，profile 页却什么都不显示

**根因**：GitHub 判定「这是 profile README 仓库」是在**创建仓库那一刻**做的。
本仓库建于 `2026-07-11 21:52`，而用户名 `aevum-orrin` → `jackiectl` 的改名 `22:01` 才生效 ——
**建的时候仓库名和当时的用户名对不上**，标记没打上；后来名字虽然匹配了，GitHub 不会追溯补。

**症状**（已可复现地验证）：`github.com/jackiectl/jackiectl` 仓库页 README 渲染正常，
但 `github.com/jackiectl` 的 HTML 里 `markdown-body` / `entry-content` / `profile-readme`
标记**全是 0**（对照组 `anuraghazra`、`sindresorhus` 都是 1）。四个官方条件全部满足也没用。

**修法**：去仓库页点 **「Share to profile」** 按钮。**只能在 UI 点，没有 API / `gh` 命令。**

**教训**：先改用户名 → **等改名生效** → 再建仓库。顺序反了就得手动补这一下。

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
| `komarev.com/ghpvc` | ✅ 用中。Profile views |
| `img.shields.io` | ✅ 用中。徽章 |
| ~~`github-readme-activity-graph.vercel.app`~~ | ⛔ **已弃用** —— 只画**最近 31 天的逐日**曲线，太琐碎。改成自建（见 §2.5） |
| **`github-readme-stats.vercel.app`**（网上最常推荐的那个） | ❌ **`DEPLOYMENT_PAUSED`** |
| **`github-profile-trophy.vercel.app`** | ❌ **`402 DEPLOYMENT_DISABLED`** |

## 2.5 贡献图：自建，按月，滚动窗口 ★

**没有任何现成卡片服务支持「按月聚合 + 滚动窗口」** —— 全都是最近 31 天的逐日图。
所以自己画：`tools/contrib.py` 从 GitHub GraphQL 的 `contributionsCollection` 拉真实逐日数据，
按月聚合，渲染成 `assets/contributions-{dark,light}.svg` **提交进仓库**。
顺带把第三方依赖也干掉了（我们已经见过两个这类服务说死就死）。

- **窗口是滚动的**：永远截止到**当前月**，往回数 `months` 个月。
  `months` 在 `data/profile.json` 的 `cards.contributions` 里，默认 **12**。改成 24 即可变两年。
- **GraphQL 单次查询最多跨 1 年** —— 所以 `fetch_daily()` **按年分块**。
  `months=24` 已实测通过（710 天跨度 / 711 天数据 / 零报错）。不分块直接报错。
- `.github/workflows/contributions.yml` 每天 04:17 UTC 重画，**只在数字真的变了才提交**。

### 🔴 两个坑（都已避开，别改回去）

1. **Action 必须以 `github-actions[bot]` 身份提交，不能用 `jackiectl`。**
   GitHub 按 commit **author** 归属贡献 —— 用你的身份提交，这个 commit 本身就变成一次 contribution，
   **把它要展示的那个数字给刷上去了**，而且每天 +1、永久自我膨胀。这是数据造假。
   （这是本项目里唯一一处**故意不遵守**「每个 commit 双署名」的地方，理由在此。）
2. **SVG 里不要写 "updated <日期>" 水印。** 日期每天都变 → 每天产生 diff → 逼出每日空提交
   → 又回到坑 1。图只在**真实贡献数变化时**才更新。

### 其他约束

- SVG 里**不能有 `<style>` 或 `<script>`** —— GitHub 渲染 README 里的 SVG 时会把它们清洗掉。
  一律用 inline `fill=` 属性。
- `contrib.py` 要在**两个 Python 上都能跑**：本机 Great Lakes 是 **3.6**（没有
  `datetime.fromisoformat`），Action 里的 ubuntu-latest 是 3.12。**别用 3.7+ 语法。**
- 本机没有 SVG 光栅化工具（无 rsvg / inkscape；ImageMagick 没编 Freetype，**文字渲染不出来**）。
  要肉眼看图：**`firefox --headless --screenshot`**（Gecko 渲染，最接近 GitHub 上的实际效果）。

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
