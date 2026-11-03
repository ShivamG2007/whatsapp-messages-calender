'use strict';

const fs = require('node:fs');
const { SELECTED_FILE, STATE_FILE, bridgeUrl, makeClient } = require('./client');
const { Bridge } = require('./bridge');
const { loadSelected, selectedIds, shouldForward, toPayload } = require('./filters');

const BACKFILL_LIMIT = Number(process.env.BACKFILL_LIMIT || 50);
const BACKFILL_HOURS = Number(process.env.BACKFILL_HOURS || 36);

const chats = loadSelected(SELECTED_FILE);
if (!chats.length) {
  console.error('No chats selected yet. Run "npm run pick" first to choose which groups the bot may read.');
  process.exit(1);
}
const allowed = selectedIds(chats);
const names = new Map(chats.map((c) => [c.id, c.name]));
const bridge = new Bridge(bridgeUrl());

let state = {};
try {
  state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
} catch {
  state = {};
}
let saveTimer = null;
function remember(chatId, ts) {
  if ((state[chatId] || 0) >= ts) return;
  state[chatId] = ts;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2)), 2000);
}

async function senderName(msg) {
  if (msg.fromMe) return 'me';
  if (msg._data && msg._data.notifyName) return msg._data.notifyName;
  try {
    const contact = await msg.getContact();
    return contact.pushname || contact.name || contact.number || '';
  } catch {
    return '';
  }
}

async function forward(msg) {
  if (!shouldForward(msg, allowed)) return;
  const payload = toPayload(msg, null, await senderName(msg));
  payload.chat_name = names.get(payload.chat_id) || '';
  bridge.send(payload);
  remember(payload.chat_id, msg.timestamp);
}

async function backfill(client) {
  const oldest = Math.floor(Date.now() / 1000) - BACKFILL_HOURS * 3600;
  let sent = 0;
  for (const id of allowed) {
    try {
      const chat = await client.getChatById(id);
      const since = Math.max(state[id] || 0, oldest);
      const messages = await chat.fetchMessages({ limit: BACKFILL_LIMIT });
      for (const msg of messages.filter((m) => m.timestamp > since).sort((a, b) => a.timestamp - b.timestamp)) {
        await forward(msg);
        sent += 1;
      }
    } catch (err) {
      console.warn(`Could not catch up on ${names.get(id) || id}: ${err.message}`);
    }
  }
  if (sent) console.log(`Caught up on ${sent} message(s) missed while the bot was off`);
}

const client = makeClient();

client.on('ready', async () => {
  console.log(`Listening (read-only) to ${chats.length} chat(s): ${chats.map((c) => c.name).join(', ')}`);
  console.log(`Sending messages to the brain at ${bridgeUrl()}`);
  await backfill(client);
});

client.on('message_create', (msg) => {
  forward(msg).catch((err) => console.error(`Failed to forward a message: ${err.message}`));
});

client.on('disconnected', (reason) => {
  console.error(`WhatsApp disconnected: ${reason}. Restart with "npm start".`);
  process.exit(1);
});

async function shutdown() {
  console.log('\nStopping listener...');
  bridge.stop();
  if (Object.keys(state).length) fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
  try {
    await client.destroy();
  } finally {
    process.exit(0);
  }
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

client.initialize();
