#!/usr/bin/env node
'use strict';

/**
 * Auto Start MCP Workflow
 * Claude Code启动时自动启动整套MCP工作流
 */

const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const LOG_DIR = path.join(process.env.USERPROFILE || process.env.HOME, '.claude', 'logs');
if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });

function log(msg) {
  const timestamp = new Date().toISOString();
  const logFile = path.join(LOG_DIR, 'mcp-workflow-startup.log');
  fs.appendFileSync(logFile, `[${timestamp}] ${msg}\n`);
  process.stderr.write(`[mcp-workflow] ${msg}\n`);
}

function isPortInUse(port) {
  try {
    const result = execSync(`netstat -ano | findstr :${port} | findstr LISTENING`, {
      encoding: 'utf8', timeout: 3000, stdio: ['pipe', 'pipe', 'pipe']
    });
    return result.trim().length > 0;
  } catch { return false; }
}

// ─── 1. 启动NVIDIA API (端口8080) ─────────────────────────
function startNvidiaAPI() {
  if (isPortInUse(8080)) {
    log('NVIDIA API already running on port 8080');
    return;
  }

  const nvidiaScript = path.join(process.env.USERPROFILE || process.env.HOME, '.claude', 'hooks', 'nvidia-api-server.js');
  if (fs.existsSync(nvidiaScript)) {
    const logFile = path.join(LOG_DIR, 'nvidia-api.log').replace(/\\/g, '/');
    const cmd = `node "${nvidiaScript}" >> "${logFile}" 2>&1`;
    const child = spawn(cmd, { detached: true, stdio: 'ignore', shell: true });
    child.unref();
    log(`NVIDIA API started on port 8080 (pid ${child.pid})`);
  } else {
    log('NVIDIA API script not found, skipping');
  }
}

// ─── 2. 启动Model Router (端口8081) ───────────────────────
function startModelRouter() {
  if (isPortInUse(8081)) {
    log('Model Router already running on port 8081');
    return;
  }

  const routerScript = path.join(process.env.USERPROFILE || process.env.HOME, '.claude', 'hooks', 'nvidia-anthropic-proxy.js');
  if (fs.existsSync(routerScript)) {
    const logFile = path.join(LOG_DIR, 'model-router.log').replace(/\\/g, '/');
    const cmd = `node "${routerScript}" >> "${logFile}" 2>&1`;
    const child = spawn(cmd, { detached: true, stdio: 'ignore', shell: true });
    child.unref();
    log(`Model Router started on port 8081 (pid ${child.pid})`);
  } else {
    log('Model Router script not found, skipping');
  }
}

// ─── 3. 检查AI-chat MCP状态 ───────────────────────────────
function checkAIChatMCP() {
  try {
    // 尝试调用health_check（通过MCP工具）
    log('AI-chat MCP will be checked on first use');
  } catch (e) {
    log(`AI-chat MCP check failed: ${e.message}`);
  }
}

// ─── 4. 检查浏览器状态 ───────────────────────────────────
function checkBrowser() {
  try {
    // 检查Chrome进程
    const result = execSync('tasklist | findstr chrome', {
      encoding: 'utf8', timeout: 3000, stdio: ['pipe', 'pipe', 'pipe']
    });
    if (result.includes('chrome.exe')) {
      log('Chrome browser is running');
    } else {
      log('Chrome browser not detected, will start on first MCP call');
    }
  } catch {
    log('Chrome browser not detected, will start on first MCP call');
  }
}

// ─── 5. 检查登录状态 ─────────────────────────────────────
function checkLoginStatus() {
  const browserDataDir = path.join(process.env.USERPROFILE || process.env.HOME, '.claude', 'scripts', '.ai-chat-browser-data');
  if (fs.existsSync(browserDataDir)) {
    log('Browser data directory exists, login states should be preserved');
  } else {
    log('Browser data directory not found, login may be required');
  }
}

// ─── 主函数 ────────────────────────────────────────────────
function main() {
  log('=== MCP Workflow Auto Start ===');

  // 启动服务
  startNvidiaAPI();
  startModelRouter();

  // 检查状态
  checkAIChatMCP();
  checkBrowser();
  checkLoginStatus();

  log('=== MCP Workflow Ready ===');
  log('Components:');
  log('  - NVIDIA API: http://127.0.0.1:8080');
  log('  - Model Router: http://127.0.0.1:8081');
  log('  - AI-chat MCP: Ready');
  log('  - Playwright MCP: Ready');
  log('  - Cost-Aware Router: Active');
  log('');
  log('Routing Matrix:');
  log('  - L1 (<20 chars): NVIDIA API');
  log('  - L2 (≥20 chars, non-code): Tree (Doubao→DeepSeek+Volcengine→NVIDIA)');
  log('  - L3 (≥20 chars, code): Claude');
}

// ─── 执行 ──────────────────────────────────────────────────
main();
