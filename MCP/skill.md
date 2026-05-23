---
name: browsehive
description: "BrowseHive浏览器AI工作流：通过browser-harness操控Chrome，与豆包/DeepSeek/欧亿AI/火山引擎协作。触发词：bh、hive、联网、打开AI平台"
---

# BrowseHive

通过 browser-harness 操控 Chrome CDP，与多 AI 平台协作。

## 触发

用户说 `bh`、`hive`、`联网`、`打开AI平台`、`打开AI工作流` 时启用。

## 工作流

1. 用 `echo 'print(list_tabs())' | browser-harness` 检查现有标签页
2. 缺失的平台用 `echo 'new_tab("URL")' | browser-harness` 打开
3. 发消息用 `bh_helper.py` 的 `send_message(msg, platform)`
4. 读响应用 `bh_helper.py` 的 `read_response(platform)`

## 平台

| 平台 | URL |
|------|-----|
| 豆包 | `https://www.doubao.com/` |
| DeepSeek | `https://chat.deepseek.com/` |
| 欧亿AI | `https://ai.rcouyi.com/home` |
| 火山引擎 | `https://exp.volcengine.com/ark` |

## 环境

- Chrome 需勾选 `chrome://inspect/#remote-debugging` 的 "Allow remote debugging"
- CDP 连接后自动最小化 Chrome 窗口（`minimize_on_ready` 配置）
- `PYTHONIOENCODING=utf-8` 必须设置

## 注意

- browser-harness 优先，失败再降级
- 中文输入用 `type_text()`，不用 `js()` 设置值（避免 surrogate 编码问题）
