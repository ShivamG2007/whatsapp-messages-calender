'use strict';

const fs = require('node:fs');

const SKIP_TYPES = new Set(['e2e_notification', 'notification_template', 'gp2', 'call_log', 'protocol', 'revoked', 'ciphertext']);

function loadSelected(file) {
  if (!fs.existsSync(file)) return [];
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  return Array.isArray(data.chats) ? data.chats : [];
}

function selectedIds(chats) {
  return new Set(chats.map((c) => c.id));
}

function chatIdOf(msg) {
  return msg.fromMe ? msg.to : msg.from;
}

function pad(n) {
  return String(n).padStart(2, '0');
}

function localStamp(unixSeconds) {
  const d = new Date(unixSeconds * 1000);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function messageText(msg) {
  const raw = msg._data || {};
  if (msg.type === 'scheduled_event_creation' || raw.eventName) {
    const parts = [`WhatsApp event created: ${raw.eventName || msg.body || 'event'}`];
    if (raw.eventStartTime) parts.push(`starts ${localStamp(raw.eventStartTime)}`);
    if (raw.eventEndTime) parts.push(`ends ${localStamp(raw.eventEndTime)}`);
    const where = raw.eventLocation && raw.eventLocation.name;
    if (where) parts.push(`at ${where}`);
    if (raw.isEventCanceled) parts.push('(CANCELLED)');
    return parts.join(', ');
  }
  return (msg.body || '').trim();
}

function shouldForward(msg, allowed) {
  if (!msg || msg.isStatus || SKIP_TYPES.has(msg.type)) return false;
  const chatId = chatIdOf(msg);
  if (!chatId || chatId === 'status@broadcast' || !allowed.has(chatId)) return false;
  return messageText(msg).length > 0;
}

function toPayload(msg, chatName, senderName) {
  return {
    id: msg.id && msg.id._serialized ? msg.id._serialized : String(msg.id),
    chat_id: chatIdOf(msg),
    chat_name: chatName || '',
    sender: msg.fromMe ? 'me' : senderName || '',
    body: messageText(msg),
    timestamp: msg.timestamp,
    from_me: Boolean(msg.fromMe),
  };
}

module.exports = { loadSelected, selectedIds, chatIdOf, messageText, shouldForward, toPayload };
