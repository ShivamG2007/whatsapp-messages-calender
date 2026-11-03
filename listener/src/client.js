'use strict';

const path = require('node:path');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const ROOT = path.resolve(__dirname, '..', '..');
const LISTENER_DIR = path.resolve(__dirname, '..');
const SELECTED_FILE = path.join(ROOT, 'config', 'selected_chats.json');
const STATE_FILE = path.join(LISTENER_DIR, '.state.json');

try {
  process.loadEnvFile(path.join(ROOT, '.env'));
} catch {
  // no .env yet, defaults are fine
}

function bridgeUrl() {
  const host = process.env.BRIDGE_HOST || '127.0.0.1';
  const port = process.env.BRIDGE_PORT || '8765';
  return process.env.BRIDGE_URL || `http://${host}:${port}`;
}

function makeClient() {
  const client = new Client({
    authStrategy: new LocalAuth({ dataPath: path.join(LISTENER_DIR, '.wwebjs_auth') }),
    puppeteer: { headless: true },
  });
  client.on('qr', (qr) => {
    console.log('\nScan this QR code with WhatsApp: Settings > Linked devices > Link a device\n');
    qrcode.generate(qr, { small: true });
  });
  client.on('authenticated', () => console.log('WhatsApp: logged in'));
  client.on('auth_failure', (msg) => console.error(`WhatsApp login failed: ${msg}. Delete listener/.wwebjs_auth and scan again.`));
  return client;
}

module.exports = { ROOT, SELECTED_FILE, STATE_FILE, bridgeUrl, makeClient };
