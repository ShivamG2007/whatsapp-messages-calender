'use strict';

class Bridge {
  constructor(baseUrl, { retryMs = 10000, maxQueue = 1000, log = console } = {}) {
    this.url = `${baseUrl.replace(/\/$/, '')}/messages`;
    this.retryMs = retryMs;
    this.maxQueue = maxQueue;
    this.queue = [];
    this.sending = false;
    this.log = log;
    this.timer = null;
  }

  send(payload) {
    if (this.queue.length >= this.maxQueue) {
      this.queue.shift();
      this.log.warn('Bridge queue full, dropped the oldest message');
    }
    this.queue.push(payload);
    return this.flush();
  }

  async flush() {
    if (this.sending) return;
    this.sending = true;
    try {
      while (this.queue.length) {
        const res = await fetch(this.url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.queue[0]),
        });
        if (!res.ok && res.status !== 422) throw new Error(`bridge answered ${res.status}`);
        if (res.status === 422) this.log.warn('Bridge rejected a message as invalid, skipping it');
        this.queue.shift();
      }
    } catch (err) {
      this.log.warn(`Brain not reachable (${err.message}). ${this.queue.length} message(s) waiting, retrying in ${this.retryMs / 1000}s`);
      clearTimeout(this.timer);
      this.timer = setTimeout(() => this.flush(), this.retryMs);
    } finally {
      this.sending = false;
    }
  }

  stop() {
    clearTimeout(this.timer);
  }
}

module.exports = { Bridge };
