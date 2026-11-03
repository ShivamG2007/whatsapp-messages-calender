'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { loadSelected, selectedIds, shouldForward, toPayload, messageText } = require('../src/filters');
const { parseChoice } = require('../src/pickChats');

const allowed = new Set(['123@g.us']);

function msg(extra = {}) {
  return {
    id: { _serialized: 'false_123@g.us_ABC' },
    from: '123@g.us',
    to: 'me@c.us',
    fromMe: false,
    type: 'chat',
    body: 'practice kal 6 baje',
    timestamp: 1793800000,
    isStatus: false,
    ...extra,
  };
}

test('forwards text from a selected group', () => {
  assert.equal(shouldForward(msg(), allowed), true);
});

test('ignores chats that were not selected', () => {
  assert.equal(shouldForward(msg({ from: '999@g.us' }), allowed), false);
});

test('ignores status updates, empty media and system messages', () => {
  assert.equal(shouldForward(msg({ isStatus: true }), allowed), false);
  assert.equal(shouldForward(msg({ type: 'image', body: '' }), allowed), false);
  assert.equal(shouldForward(msg({ type: 'e2e_notification' }), allowed), false);
});

test('my own messages in a selected group use the group as chat id', () => {
  const mine = msg({ fromMe: true, from: 'me@c.us', to: '123@g.us' });
  assert.equal(shouldForward(mine, allowed), true);
  const payload = toPayload(mine, 'Dance', 'whoever');
  assert.equal(payload.chat_id, '123@g.us');
  assert.equal(payload.sender, 'me');
  assert.equal(payload.from_me, true);
});

test('payload matches what the Python bridge expects', () => {
  const payload = toPayload(msg(), 'Dance', 'Riya');
  assert.deepEqual(Object.keys(payload).sort(), ['body', 'chat_id', 'chat_name', 'from_me', 'id', 'sender', 'timestamp']);
  assert.equal(payload.id, 'false_123@g.us_ABC');
});

test('native WhatsApp events become readable text', () => {
  const event = msg({ type: 'scheduled_event_creation', body: '', _data: { eventName: 'Jam session', eventStartTime: 1793800000 } });
  assert.match(messageText(event), /^WhatsApp event created: Jam session, starts \d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
});

test('selected chats file', () => {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'cb-')), 'sel.json');
  assert.deepEqual(loadSelected(file), []);
  fs.writeFileSync(file, JSON.stringify({ chats: [{ id: 'a@g.us', name: 'A' }] }));
  assert.deepEqual([...selectedIds(loadSelected(file))], ['a@g.us']);
});

test('picker understands lists and ranges', () => {
  assert.deepEqual(parseChoice('1, 3,5-7, 99, x', 10), [1, 3, 5, 6, 7]);
});

test('bridge keeps messages until the brain is up', async () => {
  const http = require('node:http');
  const { Bridge } = require('../src/bridge');
  const quiet = { warn() {} };
  const received = [];
  const server = http.createServer((req, res) => {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      received.push(JSON.parse(body));
      res.writeHead(202).end('{}');
    });
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const { port } = server.address();
  const down = new Bridge('http://127.0.0.1:1', { retryMs: 50, log: quiet });
  await down.send({ id: 'x' });
  assert.equal(down.queue.length, 1);
  down.stop();

  const up = new Bridge(`http://127.0.0.1:${port}`, { log: quiet });
  await up.send({ id: 'a' });
  await up.send({ id: 'b' });
  assert.deepEqual(received.map((m) => m.id), ['a', 'b']);
  assert.equal(up.queue.length, 0);
  server.close();
});
