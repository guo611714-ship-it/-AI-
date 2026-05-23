#!/usr/bin/env node
// SessionStart hook: auto-start Model Router if not running
const { execSync, spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const PORT = 8080;
const PROXY_PORT = 8081;
const HOME = process.env.USERPROFILE || process.env.HOME;
const LOG_DIR = path.join(HOME, ".claude", "logs");
const ENV_FILE = path.join(HOME, ".claude", ".env");

if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });

function isPortInUse(port) {
  try {
    if (process.platform === "win32") {
      const result = execSync(`netstat -ano | findstr :${port} | findstr LISTENING`, {
        encoding: "utf8", timeout: 3000, stdio: ["pipe", "pipe", "pipe"]
      });
      return result.trim().length > 0;
    } else {
      execSync(`lsof -i:${port}`, { timeout: 3000, stdio: "ignore" });
      return true;
    }
  } catch { return false; }
}

function loadEnvFile(filePath) {
  const env = {};
  if (!fs.existsSync(filePath)) return env;
  const lines = fs.readFileSync(filePath, "utf8").split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const idx = trimmed.indexOf("=");
    if (idx === -1) continue;
    const key = trimmed.slice(0, idx).trim();
    const val = trimmed.slice(idx + 1).trim();
    if (val) env[key] = val;
  }
  return env;
}

const envVars = loadEnvFile(ENV_FILE);

// ─── 启动 Model Router ───
if (isPortInUse(PORT)) {
  process.stderr.write(`[model-router] already running on port ${PORT}\n`);
} else {
  const configPath = path.join(HOME, ".claude", "models.yaml");
  const logFile = path.join(LOG_DIR, "model-router.log").replace(/\\/g, "/");
  const cmd = `npx claude-code-model-router start --port ${PORT} --config "${configPath}" >> "${logFile}" 2>&1`;
  const child = spawn(cmd, {
    detached: true,
    stdio: "ignore",
    env: { ...process.env, ...envVars },
    shell: true,
  });
  child.unref();
  process.stderr.write(`[model-router] started on port ${PORT} (pid ${child.pid})\n`);
}

// ─── 启动 NVIDIA→Anthropic 格式转换代理 ───
if (isPortInUse(PROXY_PORT)) {
  process.stderr.write(`[nvidia-proxy] already running on port ${PROXY_PORT}\n`);
} else {
  const proxyScript = path.join(HOME, ".claude", "hooks", "nvidia-anthropic-proxy.js");
  if (fs.existsSync(proxyScript)) {
    const proxyLogFile = path.join(LOG_DIR, "nvidia-proxy.log").replace(/\\/g, "/");
    const proxyCmd = `node "${proxyScript}" >> "${proxyLogFile}" 2>&1`;
    const proxy = spawn(proxyCmd, {
      detached: true,
      stdio: "ignore",
      env: { ...process.env, ...envVars, PROXY_PORT: String(PROXY_PORT), ROUTER_URL: `http://127.0.0.1:${PORT}` },
      shell: true,
    });
    proxy.unref();
    process.stderr.write(`[nvidia-proxy] started on port ${PROXY_PORT} (pid ${proxy.pid})\n`);
  } else {
    process.stderr.write(`[nvidia-proxy] script not found: ${proxyScript}\n`);
  }
}

process.exit(0);
