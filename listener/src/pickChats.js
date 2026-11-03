'use strict';

const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline/promises');
const { SELECTED_FILE, makeClient } = require('./client');
const { loadSelected } = require('./filters');

const SHOW = Number(process.env.PICK_SHOW || 60);

function parseChoice(input, max) {
  const picked = new Set();
  for (const part of input.split(',').map((p) => p.trim()).filter(Boolean)) {
    const range = part.match(/^(\d+)\s*-\s*(\d+)$/);
    const nums = range ? Array.from({ length: Number(range[2]) - Number(range[1]) + 1 }, (_, i) => Number(range[1]) + i) : [Number(part)];
    for (const n of nums) {
      if (Number.isInteger(n) && n >= 1 && n <= max) picked.add(n);
    }
  }
  return [...picked].sort((a, b) => a - b);
}

async function main() {
  const current = new Set(loadSelected(SELECTED_FILE).map((c) => c.id));
  const client = makeClient();
  client.on('ready', async () => {
    const all = (await client.getChats()).filter((c) => c.id._serialized !== 'status@broadcast');
    all.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    const list = all.slice(0, SHOW);

    console.log(`\nYour ${list.length} most recent chats (* = already selected):\n`);
    list.forEach((chat, i) => {
      const mark = current.has(chat.id._serialized) ? '*' : ' ';
      const kind = chat.isGroup ? 'group' : 'chat ';
      console.log(`${mark} ${String(i + 1).padStart(3)}. [${kind}] ${chat.name}`);
    });

    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    const answer = await rl.question('\nType the numbers of the chats the bot may read (e.g. 1,4,7-9). Leave empty to keep the current selection: ');
    rl.close();

    if (answer.trim()) {
      const chosen = parseChoice(answer, list.length).map((n) => list[n - 1]);
      const data = { chats: chosen.map((c) => ({ id: c.id._serialized, name: c.name, is_group: c.isGroup })) };
      fs.mkdirSync(path.dirname(SELECTED_FILE), { recursive: true });
      fs.writeFileSync(SELECTED_FILE, JSON.stringify(data, null, 2));
      console.log(`\nSaved ${chosen.length} chat(s) to config/selected_chats.json:`);
      chosen.forEach((c) => console.log(`  - ${c.name}`));
    } else {
      console.log('Selection unchanged.');
    }
    await client.destroy();
    process.exit(0);
  });
  await client.initialize();
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

module.exports = { parseChoice };
