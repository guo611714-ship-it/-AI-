#!/usr/bin/env node
'use strict';

const CAVEMAN_INSTRUCTION = `\n\n[Caveman mode active: respond like a Spartan officer. Drop all filler, preamble, restating. Use sentence fragments, bullet over prose. No "Sure!", "Happy to help", "Great question". Start with the answer directly.]`;

async function readStdin() {
  let raw = '';
  process.stdin.setEncoding('utf8');
  for await (const chunk of process.stdin) raw += chunk;
  return raw;
}

async function main() {
  try {
    const raw = await readStdin();
    if (!raw.trim()) process.exit(0);

    const data = JSON.parse(raw);
    const prompt = data.prompt || data.tool_input?.prompt || '';
    if (!prompt) process.exit(0);

    const updatedPrompt = prompt + CAVEMAN_INSTRUCTION;

    const response = {
      hookSpecificOutput: {
        hookEventName: 'UserPromptSubmit',
        updatedPrompt: updatedPrompt,
      },
    };
    process.stdout.write(JSON.stringify(response));
    process.exit(0);
  } catch {
    process.exit(0);
  }
}

main();
