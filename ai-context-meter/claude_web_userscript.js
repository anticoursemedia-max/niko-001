// ==UserScript==
// @name         AI Context Meter (web reporter)
// @namespace    ai-context-meter
// @version      1.0
// @description  Estimates conversation size on claude.ai / ChatGPT and reports it to the local meter
// @match        https://claude.ai/*
// @match        https://chatgpt.com/*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// ==/UserScript==
(function () {
  'use strict';
  const isClaude = location.hostname.includes('claude.ai');
  const SOURCE = isClaude ? 'Claude.ai' : 'ChatGPT';
  const WINDOW = isClaude ? 200000 : 128000; // adjust to your plan/model
  const CHARS_PER_TOKEN = 3.5;               // rough estimate

  function report() {
    const el = document.querySelector('main');
    if (!el) return;
    const used = Math.round(el.innerText.length / CHARS_PER_TOKEN);
    GM_xmlhttpRequest({
      method: 'POST',
      url: 'http://127.0.0.1:8765/update',
      headers: { 'Content-Type': 'application/json' },
      data: JSON.stringify({ source: SOURCE, used: used, window: WINDOW }),
    });
  }
  setInterval(report, 5000);
})();
