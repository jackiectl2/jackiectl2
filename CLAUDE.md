# CLAUDE.md — profile-readme

GitHub **profile README** 仓库: `github.com/jackiectl/jackiectl`
(⚠ 仓库名必须与用户名**完全相同**, `README.md` 才会显示在 profile 页顶部. 别改名.)

父目录 `personal_website/CLAUDE.md` 和全局 `~/.claude/CLAUDE.md` 会自动叠加, 这里不重复.

---

## 0. 🔴 踩过的坑: README 在仓库页正常, profile 页却什么都不显示

**根因**: GitHub 判定 "这是 profile README 仓库" 是在**创建仓库那一刻**做的.
本仓库建于 `2026-07-11 21:52`, 而用户名 `aevum-orrin` → `jackiectl` 的改名 `22:01` 才生效 ——
**建的时候仓库名和当时的用户名对不上**, 标记没打上; 后来名字虽然匹配了, GitHub 不会追溯补.

**症状**(已可复现地验证): `github.com/jackiectl/jackiectl` 仓库页 README 渲染正常,
但 `github.com/jackiectl` 的 HTML 里 `markdown-body` / `entry-content` / `profile-readme`
标记**全是 0**(对照组 `anuraghazra`, `sindresorhus` 都是 1). 四个官方条件全部满足也没用.

**修法**: 去仓库页点 **"Share to profile"** 按钮. **只能在 UI 点, 没有 API / `gh` 命令.**

**教训**: 先改用户名 → **等改名生效** → 再建仓库. 顺序反了就得手动补这一下.

---

## 1. 最重要的一条: README.md 是**生成物**, 不要手改

```
data/profile.json   ← 唯一可编辑的内容源 (PROFILE.md 的机读投影)
       ↓  python3 build.py
README.md           ← 生成物. 手改会被下次 build 覆盖
```

- **加一个项目 / 一条 timeline** = 往 `data/profile.json` 加一条 → `python3 build.py`.
  **不改 `build.py`, 不改 README.** 这就是铁律 B 在本仓库的落地.
- `python3 build.py --check` → README 与 JSON 不一致时 exit 1 (可做 CI).
- 事实源仍是 `../PROFILE.md`. **先改 PROFILE.md, 再把改动镜像进 `profile.json`.**

## 2. 卡片: 三张全部自建 (2026-07-22)

**profile 上的三张卡现在都由本仓库的 Action 生成, 提交成静态 SVG, 运行时零第三方请求.**

| 卡片 | 原来 | 现在 | 生成器 |
|---|---|---|---|
| Stats | `github-stats-extended.vercel.app` | 自己的 Action | `stats-organization/github-readme-stats-action` (钉死 SHA) |
| Streak | `streak-stats.demolab.com` | 自己的代码 | `tools/streak.py` |
| 贡献图 | `github-readme-activity-graph.vercel.app` | 自己的代码 | `tools/contrib.py` |

**为什么值得自建** (三条都是实测踩出来的, 不是洁癖):
1. **服务会死.** `github-readme-stats` 和 `github-profile-trophy` 都已 `DEPLOYMENT_PAUSED` / `402`.
2. **错误会被缓存一整天.** streak 服务上游挂时返回一张 "Failed to retrieve contributions" 哭脸卡,
   那是**合法 200 SVG** 且带 `cache-control: max-age=86400` —— camo 照缓存, 哭脸在 profile 上挂满 24 小时.
3. **托管版永远只看得到公开数据.** 详见下面 §2.1.

**代价**: 生成器代码仍是第三方的 (stats 那张), 但**钉死到 commit SHA**, 不会在背后变.
`tools/streak.py` / `tools/contrib.py` 是完全自己写的.

### 剩下的第三方 (都不值得或不可能收回)

| | 为什么留着 |
|---|---|
| `komarev.com/ghpvc` (Profile Views) | **物理上不能自建.** 计数器必须靠真实访客直接命中才能 +1; 一缓存/烤成静态, 计数就冻死 |
| `img.shields.io` × 4 | 纯静态色块 + followers 数, 缓存 5 天, 极稳, 从没出过问题 |

### 🔴 只能有一个 workflow

`contributions.yml` 和 `stats-cards.yml` 曾经并存, **两个都写 `assets/` 且都 push** ——
实测撞过一次 (push rejected, 要 rebase). **已合并成单个 `stats-cards.yml`**, 一次跑完三张卡 + rebuild README, 只提交一次.

## 2.1 私有数据: STATS_PAT

托管卡片是用**别人的 token** 算的, 所以**永远只能看到公开数据**. 实测差距很大:

| | GITHUB_TOKEN (公开) | STATS_PAT (含私有) |
|---|---|---|
| Total Commits | 277 | **540** |
| Total PRs | 2 | **16** |
| Rank | C+ | **B-** |

用户 34 个仓库里约 12 个是私有的, `restrictedContributionsCount` 占总贡献的 ~56%.

- **secret 名 `STATS_PAT`**, classic token, scope = `repo` + `read:user`.
  workflow 写的是 `${{ secrets.STATS_PAT || secrets.GITHUB_TOKEN }}` —— **有就用, 没有就退回公开模式,
  不会崩**. 加/删这个 secret 即可切换, 不用改代码.
- ⚠ **fine-grained token 不行**: 官方文档明写 "This limits the scope of commits to public
  repositories only". 想要私有数据只能 classic + `repo`.
- ⚠ **托管版那个 "GitHub Private Access" 按钮别点**: 它的 OAuth URL 是 `scope=user,repo`
  (见 `apps/frontend/src/constants.ts`), 等于把**全部私有仓库的读写权**交给第三方 Vercel 应用.
  自建拿到的效果完全一样, 但 token 在自己账号里.
- 🔴 **第三方 action 必须钉死 commit SHA, 不能用 `@v2`**. 那一步会拿到 `STATS_PAT`;
  tag 可被维护者随时重指, 等于接收 token 的代码能在背后换掉.
- token 2027-07-22 过期. 过期后自动退回公开模式 (不会崩), 重新生成换上即可.

## 2.5 贡献图的三种模式

`cards.active_graph` 三选一, 都由 `tools/contrib.py` 生成同一对资产文件:

| 值 | 画什么 |
|---|---|
| `local_daily` ★ 当前 | 最近 `days` 天的**面积图** (仿第三方那张的版式, 用自己的配色) |
| `local_monthly` | 最近 `months` 个月的**柱状图**. 等攒够一年历史再切 |
| `hosted` | 退回 `github-readme-activity-graph.vercel.app` |

- **窗口都是滚动的**, 永远截止到今天.
- **GraphQL 单次查询最多跨 1 年** —— 所以 `fetch_daily()` **按年分块**.
  `months=24` 已实测通过 (710 天跨度 / 711 天数据 / 零报错). 不分块直接报错.
- Y 轴用 `nice_axis()` 取**整十步长** (0/10/../70), 不是把最大值等分 5 份 (会得到 0/16/../80).

### 🔴 两个坑 (都已避开, 别改回去)

1. **Action 必须以 `github-actions[bot]` 身份提交, 不能用 `jackiectl`.**
   GitHub 按 commit **author** 归属贡献 —— 用你的身份提交, 这个 commit 本身就变成一次 contribution,
   **把它要展示的那个数字给刷上去了**, 而且每天 +1, 永久自我膨胀. 这是数据造假.
   (这是本项目里唯一一处**故意不遵守**"每个 commit 双署名" 的地方, 理由在此.)
2. **SVG 里不要写 "updated <日期>" 水印.** 日期每天都变 → 每天产生 diff → 逼出每日空提交
   → 又回到坑 1. 图只在**真实贡献数变化时**才更新.

### 其他约束

- SVG 里**不能有 `<style>` 或 `<script>`** —— GitHub 渲染 README 里的 SVG 时会把它们清洗掉.
  一律用 inline `fill=` 属性.
- **README 里引用这两个 SVG 用相对路径 (`assets/...`) 是安全的, 不用换成绝对 raw URL.**
  GitHub 在 **profile 页**上也会按仓库上下文把它重写成 `/jackiectl/jackiectl/raw/main/assets/...`.
  已用正面对照验证: `codeSTACKr` 的 profile 页把 `img/globe-light.svg` 重写后**返回 200**.
  好处: 走 `/raw/` 不过 camo, **没有缓存陈旧问题**, bot 一提交就立刻更新.
- `contrib.py` 要在**两个 Python 上都能跑**: 本机 Great Lakes 是 **3.6**(没有
  `datetime.fromisoformat`), Action 里的 ubuntu-latest 是 3.12. **别用 3.7+ 语法.**
- 本机没有 SVG 光栅化工具 (无 rsvg / inkscape; ImageMagick 没编 Freetype, **文字渲染不出来**).
  要肉眼看图: **`firefox --headless --screenshot`**(Gecko 渲染, 最接近 GitHub 上的实际效果).

**`top-langs` 卡片故意没放** —— 现在三个仓库都是空的, 渲染出来是张只有标题的空卡.
等 `site-2d` / `site-3d` 推上去, 有语言统计了再加 (往 `profile.json` 的 `cards` 里加一条即可).

### light / dark 双主题

GitHub README 会剥掉 `<style>` 和 class, 所以 `prefers-color-scheme` 只能靠
`<picture>` + `<source media=...>` 这个结构化钩子实现 (`build.py: themed_card()`).
**不能只挂一张深色卡** —— 一半读者是 light mode, 深色卡在白底上是黑底一块.

用 `gruvbox` / `gruvbox_light`(暖色, 呼应点心主题). 已验证 light 主题的正文
fill 是 `#427b58`(深绿) 不是浅灰, 白底上读得清.

## 3. workflow: `.github/workflows/stats-cards.yml` (唯一一个)

`cron: "7 */3 * * *"`(每三小时) + `workflow_dispatch` + 改到 `tools/**` / `data/profile.json` / 自身时触发.
一次跑完: 报告用了哪个 token → 生成 stats(暗/亮) → streak → 贡献图 → `build.py` → **只在有变化时提交一次**.

- ⚠ **我的 PAT 触发不了它** (`Workflows: RW` 是改文件, 运行要 `Actions` 权限, 没有).
  要手动跑: 用户在 Actions 页点, 或推一个动到上述路径的 commit.
- 之前一度有两个 workflow 并存, **实测撞车过** (push rejected). 现在只留这一个.

### 🔴 schedule 会迟到几小时, push 秒跑

实测 (2026-07-23): `cron: "37 4 * * *"` 那次**实际 `07:17 UTC` 才跑, 迟到 2h40m**;
次日 `04:37 UTC` 那次到 `05:20 UTC` 仍未触发. 同期 6 次 `push` 触发的全部立即执行.
(这一段的时间戳一律是 **UTC**, 因为 GitHub 的 cron 和 run 日志都只用 UTC; 本机是 EDT, 差 4 小时.)
GitHub 的 scheduled workflow 是排队制, 高负载时整点最挤 —— 所以

1. **cron 分钟选 `7` 这种非整点**, 避开最挤的槽;
2. **判断"卡片是不是坏了"之前, 先看 `gh run list` 里最后一次成功运行的时间戳**.
   卡上的数字只反映**那一刻**的事实, 不是"现在". 已经误判过一次:
   Total Issues 显示 0, 而当时 9 个 issue **全部创建于最后一次运行之后** —— 代码没问题, 是卡过期.
3. 要立刻刷新: 推一个动到 `tools/**` 的 commit (push 链路不排队), 或在 Actions 页点 Run workflow.

## 4. 状态 / 待办

- ✅ Skills 里的 `ML & Data`(PyTorch / scikit-learn / Gaussian Processes / Foundation-Model
  Fine-Tuning / HDF5) 和 `Slurm / HPC` **已由用户确认属实**(2026-07-11).
  🔴 **但 `cv/` 里还没补** —— 见 `PROFILE.md` §6 的红字.
- ✅ 三张卡已全部自建并线上验证 (`/raw/` 返回 200 image/svg+xml).
- Publications 现在是 "In preparation."(铁律 B ④ 要求板块常驻). 有论文了往
  `profile.json` 的 `publications: []` 里加, 板块自动从 "In preparation" 切成真条目 —— 已实测.
