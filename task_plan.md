# GTA6 Guide 修复计划

## 目标
修复 4 个问题：favicon、404 页、about 接入构建、分析工具

## 步骤

### 1. 加 favicon
- 在 4 个模板 `<head>` 中加入内联 SVG favicon（GTA6 霓虹风格 🌴）
- 模板：generic.html, mission.html, item.html, index-template.html
- 同时修改手写的 about.html（在接入构建前先保持一致）

### 2. 加 404 页
- 在 build.py 中新增 `gen_404()` 函数
- 用 generic.html 模板生成 404.html
- 内容：友好的"页面未找到" + 返回首页链接

### 3. about.html 接入构建脚本
- 在 build.py 的 `main()` 中添加 `gen_generic("about.html", ...)` 调用
- 把现有 about.html 的内容转成构建参数
- 运行 `python scripts/build.py` 重新生成所有页面
- 确保 nav 里 about 链接指向正确（目前模板 footer 已有 about 链接）

### 4. 装分析工具
- 在 4 个模板 `<head>` 中加入 Microsoft Clarity 脚本
- 复用 rimworld-guide 同一个 Clarity ID（都是 yxhtl.com 域下，同一账号可追踪）
