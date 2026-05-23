# MCP工作流整合架构

## 架构图

```
用户请求
    ↓
[Cost-Aware Router Hook] 复杂度评估
    ↓
┌─────────────────────────────────────┐
│ L1 简单（<20字符）                   │
│ → NVIDIA API (端口8080)             │
│ → 节省100% Claude token             │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ L2 中等（≥20字符，非代码）          │
│ 树状调用：                          │
│   Layer1: 豆包（初步处理）          │
│   Layer2: DeepSeek + 火山引擎（并行）│
│   Layer3: NVIDIA（整合输出）        │
│ → 节省100% Claude token             │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ L3 复杂（代码任务）                  │
│ → Claude (原生)                     │
│ → 核心代码/架构设计                 │
└─────────────────────────────────────┘
```

## 组件清单

### 1. Claude Code (大脑)
- 决策推理
- 代码生成
- 优化迭代
- Hook系统

### 2. AI-chat MCP (身体)
- **工具数量**: 85个
- **代码行数**: 4756行
- **核心功能**:
  - 对话: ask_doubao, ask_deepseek, ask_volcengine, smart_ask, ask_with_fallback
  - 批量: batch_ask, batch_ask_advanced, execute_split
  - 工作流: create_task_chain, run_workflow, list_workflow_templates
  - 会话: check_login, refresh_sessions, open_all_platforms
  - 缓存: warmup_cache, clear_cache, invalidate_cache
  - 监控: health_check, get_system_overview, get_health_trend
  - 容错: get_circuit_breaker_status, reset_circuit_breaker
  - 统计: get_perf_dashboard, get_cost_stats, get_token_savings_report
  - 指纹: rotate_fingerprint, get_fingerprint_status
  - 配置: get_config, set_config, save_session_snapshot

### 3. Playwright MCP (眼睛)
- 浏览器自动化
- 页面抓取
- 截图验证
- DOM操作

### 4. Cost-Aware Router Hook (路由大脑)
- **复杂度评估**: 基于字符数和关键词
- **路由矩阵**:
  - L1 (<20字符): NVIDIA API
  - L2 (≥20字符, 非代码): 树状调用
  - L3 (≥20字符, 代码): Claude
- **树状调用逻辑**:
  - Layer1: 豆包初步处理
  - Layer2: DeepSeek + 火山引擎并行深度分析
  - Layer3: NVIDIA整合输出

### 5. NVIDIA API (整合器)
- 端口: 8080
- 功能: 整合多个模型的回复
- 成本: $0.0001/1K tokens

## 平台配置

| 平台 | 模式 | 功能 | 登录状态 |
|------|------|------|----------|
| 豆包 | 超能模式 | 中文润色、内容生成、图片理解 | ✅ 已登录 |
| DeepSeek | 专家模式+深度思考+智能搜索 | 技术调研、复杂分析 | ✅ 已登录 |
| 火山引擎 | doubao-seed-2.0-pro | 实验报告、专业文档、图片理解 | ✅ 已登录 |
| NVIDIA API | 整合模式 | 多模型回复整合 | ✅ 运行中 |

## 成本优化

| 任务类型 | 模型 | 成本/1K tokens | 节省比例 |
|----------|------|----------------|----------|
| L1 简单 | NVIDIA | $0.0001 | 100% |
| L2 中等 | 豆包+DeepSeek+火山引擎+NVIDIA | $0 | 100% |
| L3 复杂 | Claude | $0.015 | 0% |

## 故障回退

```
NVIDIA API 失败
    ↓
豆包超能模式
    ↓
火山引擎 doubao-seed-2.0-pro
    ↓
DeepSeek 专家模式
    ↓
Claude (原生)
```

## 监控指标

```json
{
  "routing_decisions": {
    "L1_nvidia": 0,
    "L2_tree": 0,
    "L3_claude": 0
  },
  "cost_savings": "0%",
  "avg_latency_ms": 0,
  "fallback_count": 0,
  "cache_hit_rate": "0%"
}
```

## 使用示例

### L1 简单任务
```
用户: "你好"
→ 路由: NVIDIA API
→ 响应: 快速回复
```

### L2 中等任务
```
用户: "帮我润色这段文字，让它更加通顺自然，同时保持原文的意思不变"
→ 路由: 树状调用
→ 流程:
  1. 豆包初步处理
  2. DeepSeek + 火山引擎并行深度分析
  3. NVIDIA整合输出
→ 响应: 高质量润色结果
```

### L3 复杂任务
```
用户: "帮我写一个Python函数来处理这个bug，需要修复内存泄漏问题"
→ 路由: Claude
→ 响应: 专业代码解决方案
```

## 文件清单

| 文件 | 位置 | 功能 |
|------|------|------|
| ai-chat-mcp.py | ~/.claude/scripts/ | MCP服务器主体 |
| cost-aware-router-hook.js | ~/.claude/hooks/ | 路由hook脚本 |
| cost-aware-mcp-router.yaml | ~/.claude/ | 路由配置文件 |
| auto-start-mcp-workflow.js | ~/.claude/hooks/ | 自动启动脚本 |
| stop-mcp-workflow.js | ~/.claude/hooks/ | 停止脚本 |
| settings.json | ~/.claude/ | 全局配置 |
| settings.json | 项目目录/.claude/ | 项目级配置 |

## 自动启动

Claude Code启动时自动执行：
1. 启动NVIDIA API (端口8080)
2. 启动Model Router (端口8081)
3. 检查AI-chat MCP状态
4. 检查浏览器状态
5. 检查登录状态
6. 激活Cost-Aware Router Hook

## 手动控制

```bash
# 启动MCP工作流
node ~/.claude/hooks/auto-start-mcp-workflow.js

# 停止MCP工作流
node ~/.claude/hooks/stop-mcp-workflow.js
```

## 迭代历程

| 版本 | 工具数 | 核心优化 |
|------|--------|----------|
| 原始 | 18 | 基础对话 |
| 当前 | 85 | +67工具 |
| 整合后 | 85+ | +路由hook+树状调用+NVIDIA整合 |

## 待优化

1. **持久化队列**: 重启后任务队列丢失
2. **AQL集成**: 计划中的查询语言
3. **无头模式**: CI/CD场景需手动配置
4. **文件拆分**: 4756行单文件，维护成本高
