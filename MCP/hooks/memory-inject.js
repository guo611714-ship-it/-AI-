#!/usr/bin/env node
/**
 * Memory Inject Hook - SessionStart
 * Injects learned memories into Claude's context at session start.
 * Reads from ChromaDB via Python script.
 */

const { execSync } = require('child_process');
const path = require('path');
const os = require('os');

const PYTHON = path.join(os.homedir(), '.claude', 'memory', 'venv', 'Scripts', 'python.exe');
const SCRIPT = path.join(os.homedir(), '.claude', 'memory', 'scripts', 'memory_store.py');

function readStdin() {
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => resolve(data));
  });
}

async function main() {
  try {
    const input = await readStdin();
    const hookData = JSON.parse(input);

    // Get memory context
    let context = '';
    try {
      context = execSync(`"${PYTHON}" "${SCRIPT}" context claude-user 2000`, {
        encoding: 'utf8',
        timeout: 5000,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
      }).trim();
    } catch (e) {
      // Silent fail - memories are optional
    }

    if (!context) {
      process.exit(0);
    }

    const response = {
      hookSpecificOutput: {
        hookEventName: 'SessionStart',
        additionalContext: `\n\n${context}\n`
      }
    };

    process.stdout.write(JSON.stringify(response));
  } catch (e) {
    process.exit(0);
  }
}

main();
