# 发现记录

## rimworld-guide 参考
- favicon：内联 SVG，`<link rel="icon" href="data:image/svg+xml,...🪐...">`，放在 `<head>` 末尾
- Clarity ID：`x9iflmg36h`，脚本放在 `</head>` 前
- 404 页：手写 HTML，和普通页结构一致

## gta6-guide 模板结构
- 4 个模板：generic.html（通用页、首页）、mission.html（任务详情）、item.html（武器/车辆/收集品）、index-template.html（列表页）
- 构建流程：`python scripts/build.py` → 读 CSV → 套模板 → 写入 HTML → 生成 sitemap
- 手写文件：about.html（不在构建流程里）、index.html（被构建覆盖）
- 构建脚本的 `gen_generic()` 函数负责生成 cheats.html、money-guide.html、online/index.html、pre-order.html、privacy.html
- footer 中已有 about 链接

## Clarity 注意
- rimworld-guide.yxhtl.com 和 gta6.yxhtl.com 是不同子域名
- Clarity 同一个 project ID 可以跨子域名追踪
- 如果以后要分开看数据，去 Clarity 后台建新 project 换 ID 就行
