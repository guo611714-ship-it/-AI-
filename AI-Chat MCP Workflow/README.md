# AI-Chat MCP Workflow

多平台AI协作MCP工作流，基于Claude Code + ai-chat-mcp.py + browser-harness架构。

## 架构

```
Claude Code (大脑)
    ↓ MCP协议
ai-chat-mcp.py (身体, 76个工具)
    ↓ browser-harness (眼睛+手臂, CDP直连)
    ↓ cost-aware-llm-pipeline (任务复杂度判断)
豆包 / DeepSeek / 欧亿AI / 火山引擎 (平台)
```

## 平台能力

| 平台 | 能力标签 | 用途 |
|------|----------|------|
| 豆包 | 中文/润色/改写/文案/创意/翻译 | 中文内容生成 |
| 火山引擎 | 代码/编程/算法/技术/分析/推理 | 技术调研分析 |
| 欧亿AI | 图像/思维导图/可视化 | 图像生成 |
| DeepSeek | 报告/文档/专业/论文/实验 | 专业文档 |

## smart_ask路由逻辑

- **L1** (<20字符): 直接发送到默认平台
- **L2** (非代码任务): 按平台能力匹配，支持树状调用（主平台→辅助平台→整合）
- **L3** (代码任务): 发送到火山引擎(技术平台)

## 核心特性

- 请求合并、自适应限流、重试预算
- 响应压缩、近似去重
- 智能路由、树状调用
- 任务链、工作流模板

## 文件结构

```
AI-Chat MCP Workflow/
├── scripts/
│   ├── ai-chat-mcp.py          # MCP Server主文件 (76工具, ~4384行)
│   ├── browser_agent.py         # browser-harness浏览器操控
│   ├── mcp-test-optimize-loop.py # 测试-优化循环
│   ├── self-optimization-loop.py # 自优化循环
│   ├── ai-chat-mcp.bat          # Windows启动脚本
│   ├── chrome-cdp-launcher.ps1  # Chrome CDP启动器
│   ├── searxng-search.ps1       # SearXNG搜索
│   └── searxng-search.sh        # SearXNG搜索(Linux)
├── hooks/
│   └── cost-aware-router-hook.js # 复杂度路由Hook
├── .mcp.json                    # MCP配置 (需填入自己的token)
└── README.md
```

## 快速开始

1. 复制 `.mcp.json` 到项目根目录
2. 填入你的 GitHub Token 和 Firecrawl API Key
3. 安装依赖: `pip install mcp websockets`
4. 启动: `python "AI-Chat MCP Workflow/scripts/ai-chat-mcp.py"`
