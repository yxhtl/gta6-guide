# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

GTA6 Guide — 静态攻略网站，Python 构建脚本读取 CSV 数据 + HTML 模板 → 生成纯静态页面，托管于 GitHub Pages。

**线上地址**: `https://gta6.yxhtl.com`
**部署方式**: push master 即上线（GitHub Pages 自动构建）

## 常用命令

```bash
python scripts/build.py    # 构建全站（清理旧 HTML → 生成页面 → sitemap + robots）
```

构建输出 43 个 URL：首页、pre-order、cheats、money-guide、privacy、online、32 个 mission 详情页、5 个分类列表页 + sitemap.xml + robots.txt。

## 架构

### 数据流

```
data/*.csv  →  build.py  →  templates/*.html  →  生成的 HTML 页面
```

- **`data/`** — CSV 数据源（missions.csv 有 32 条，weapons/vehicles/collectibles/side-missions 目前为空）
- **`templates/`** — HTML 模板，用 `{{PLACEHOLDER}}` 语法
- **`scripts/build.py`** — 唯一的构建脚本，约 1100 行，包含所有页面生成逻辑
- **`css/style.css`** — 全局样式，Vice City 霓虹合成波主题

### 模板系统

用 `replace_all(text, vars_dict)` 做纯字符串替换（不是 Jinja，是自己写的）。`{{KEY}}` 默认走 `html.escape()`，要跳过转义用 `safe_html()` 包裹。

**4 个模板文件：**

| 模板 | 用在哪 | 备注 |
|------|--------|------|
| `generic.html` | 首页、pre-order、cheats、money-guide、privacy、online | 最通用，有 `PREORDER_ACTIVE`/`CHEATS_ACTIVE`/`MONEY_ACTIVE` 导航高亮 |
| `mission.html` | 32 个主线 + N 个支线任务详情页 | 含 Structured Data (ld+json)，面包屑 + 上下页导航 |
| `item.html` | weapons/vehicles/collectibles 详情页 | stats-grid 布局，同样含 ld+json |
| `index-template.html` | 分类列表页（story-missions/、weapons/ 等） | grid-list 布局 |

所有模板共享同一套页面过渡动画（overlay: cover → covering → reveal，`overlay-art.svg`），由内联 JS 驱动。

### build.py 核心函数

- `gen_homepage()` — 首页（preorder-hero + 双栏引导 + category-grid）
- `gen_generic(filename, title, h1, meta, content, active_nav)` — 通用内容页
- `gen_mission(row, i, prev, next)` — 单任务页
- `gen_item(row, category)` — 单武器/载具页
- `gen_collectible(row)` — 单收集品页
- `gen_side_mission(row, i, prev, next)` — 单支线任务页
- `gen_index(category_name, items, css_path, home_path)` — 分类列表页
- `gen_sitemap(pages)` / `gen_robots()` — SEO 文件

### SEO 多样性

每个页面类型有 3 个结构变体（`hash_seed(name) % 3`），段落顺序和标题措辞不同，避免全部页面结构一模一样。同一页面多次构建结果一致（基于 MD5 取模）。

### 页面过渡动画

三态 overlay 系统，阻止内部链接跳转时的白屏闪烁：
1. `cover` — 伪装标签页滑入遮住整个页面（280ms 后跳转）
2. `covering` — 到达新页面时先遮住，然后
3. `reveal` — 滑走露出新页面内容（transitionend 或 600ms 兜底清理）

只拦截内部 `.html` 和目录链接，`#` 锚点、外链、`download` 属性不走过渡。

### 生成文件（已 gitignored，但实际在仓库中）

构建产物直接输出到仓库根目录和子目录（story-missions/、weapons/ 等），push 到 GitHub Pages 即上线。`sitemap.xml` 和 `robots.txt` 每次构建重新生成。

## 重要约定

- **Python f-string 中的 JS 花括号**：JS 代码里的 `{` 要写成 `{{`，`}` 要写成 `}}`，否则 Python 解析报错
- **路径前缀**：根目录页面 `CSS_PATH=""`, `HOME_PATH=""`；子目录页面用 `"../"`；online/ 目录用 `"../"`
- **导航高亮**：`MISSIONS_ACTIVE`、`WEAPONS_ACTIVE`、`VEHICLES_ACTIVE`、`PREORDER_ACTIVE` 等设为 `' class="active"'` 或空字符串
- **根目录特殊文件**：`CNAME`（`gta6.yxhtl.com`）、`BingSiteAuth.xml`（Bing Webmaster 验证）必须放在仓库根目录
- **CSV 字段约束**：mission CSV 的 `steps` 用 `|` 分隔子步骤，`tips` 和 `trivia` 为可选字段
- **预处理内容**：pre-order 页面所有价格/版本/渠道数据均为预测，6 月 25 日预购开启后需替换为真实数据
