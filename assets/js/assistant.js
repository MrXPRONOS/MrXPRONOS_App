// assistant.js - Mr XPRONOS Assistant IA (Version Premium corrigée)
// Plein écran, couleurs conformes, liens bleus, espacement, F CFA, cache, persistance.
// Corrections :
// - nettoyage automatique des réponses ```html ... ```
// - amélioration du rendu mobile
// - tableaux plus lisibles
// - couleurs premium harmonisées
// - meilleure taille de police

(function() {
  "use strict";

  // ============================================================
  // CONFIGURATION
  // ============================================================
  const API_BASE = 'https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/assistant';
  const DEFAULT_SUGGESTIONS = [];
  const CACHE_TTL = 24 * 60 * 60 * 1000;

  let responseCache = new Map();

  try {
    const cached = localStorage.getItem('assistant_response_cache');
    if (cached) {
      const parsed = JSON.parse(cached);
      responseCache = new Map(parsed);
    }
  } catch (e) {
    console.warn('Erreur chargement cache', e);
  }

  function cleanExpiredCache() {
    const now = Date.now();
    for (let [key, value] of responseCache.entries()) {
      if (now - value.timestamp > CACHE_TTL) {
        responseCache.delete(key);
      }
    }
    saveCache();
  }
  cleanExpiredCache();

  let isOpen = false;
  let userId = localStorage.getItem('assistant_user_id') || 'user_' + Math.random().toString(36).substr(2, 9);
  localStorage.setItem('assistant_user_id', userId);

  const MESSAGES_STORAGE_KEY = 'assistant_messages';

  // ============================================================
  // STYLES
  // ============================================================
  const style = document.createElement('style');
  style.textContent = `
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');

  :root {
    --gold: #D4AF37;
    --gold-light: #FFD700;
    --gold-dark: #B8941F;
    --bg-dark: #0D0D0D;
    --bg-card: #1A1A1A;
    --bg-elevated: #252525;
    --text-primary: #FFFFFF;
    --text-secondary: #A0A0A0;
    --accent-green: #22C55E;
    --accent-red: #EF4444;
    --blue-link: #5d8cff;
    --shadow-gold: 0 4px 20px rgba(212, 175, 55, 0.3);
    --border-gold: 1px solid rgba(212, 175, 55, 0.3);
  }

  * {
    box-sizing: border-box;
  }

  .assistant-button {
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 50%, var(--gold) 100%);
    box-shadow: var(--shadow-gold), 0 4px 15px rgba(0,0,0,0.5);
    cursor: pointer;
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border: 2px solid rgba(255,255,255,0.2);
    animation: pulse-gold 2s infinite;
  }

  .assistant-button.hidden {
    display: none !important;
  }

  @keyframes pulse-gold {
    0%, 100% { box-shadow: var(--shadow-gold), 0 0 0 0 rgba(212, 175, 55, 0.4); }
    50% { box-shadow: var(--shadow-gold), 0 0 0 15px rgba(212, 175, 55, 0); }
  }

  .assistant-button:hover {
    transform: scale(1.1) rotate(5deg);
    background: linear-gradient(135deg, var(--gold-light) 0%, var(--gold) 100%);
  }

  .assistant-button img {
    width: 30px;
    height: 30px;
    filter: brightness(0) invert(1);
  }

  .assistant-window {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: linear-gradient(180deg, #121212 0%, #0d0d0d 100%);
    backdrop-filter: blur(20px);
    border: none;
    z-index: 9999;
    display: none;
    flex-direction: column;
    overflow: hidden;
    color: var(--text-primary);
    font-family: 'Montserrat', sans-serif;
    animation: fade-in 0.3s ease-out;
  }

  @keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .assistant-window.open {
    display: flex;
  }

  .assistant-header {
    background: linear-gradient(135deg, #111111 0%, #1b1b1b 100%);
    padding: 16px 20px;
    border-bottom: 1px solid rgba(212,175,55,0.45);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .assistant-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .assistant-avatar {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--gold), var(--gold-light));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    font-weight: 600;
    color: var(--bg-dark);
    box-shadow: 0 2px 8px rgba(212, 175, 55, 0.3);
  }

  .assistant-header-info h3 {
    margin: 0;
    color: var(--gold-light);
    font-size: 1.2rem;
    font-weight: 700;
  }

  .assistant-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.9rem;
    color: var(--accent-green);
    margin-top: 2px;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    background: var(--accent-green);
    border-radius: 50%;
    animation: pulse-status 2s infinite;
  }

  @keyframes pulse-status {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .assistant-close {
    background: transparent;
    border: none;
    color: var(--gold);
    font-size: 2rem;
    cursor: pointer;
    line-height: 1;
    transition: transform 0.2s;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .assistant-close:hover {
    transform: scale(1.2) rotate(90deg);
    color: var(--accent-red);
  }

  .clear-cache {
    background: transparent;
    border: none;
    color: var(--gold);
    font-size: 1.2rem;
    cursor: pointer;
    margin-right: 10px;
    transition: transform 0.2s;
  }

  .clear-cache:hover {
    transform: scale(1.2);
  }

  .assistant-messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: linear-gradient(180deg, #151515 0%, #0c0c0c 100%);
    scroll-behavior: smooth;
    position: relative;
  }

  .assistant-messages::-webkit-scrollbar {
    width: 6px;
  }

  .assistant-messages::-webkit-scrollbar-track {
    background: transparent;
  }

  .assistant-messages::-webkit-scrollbar-thumb {
    background: var(--gold);
    border-radius: 3px;
  }

  .message {
    max-width: 92%;
    padding: 0;
    border-radius: 16px;
    word-wrap: break-word;
    font-size: 0.95rem;
    line-height: 1.5;
    animation: message-appear 0.3s ease-out;
  }

  @keyframes message-appear {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .message.user {
    align-self: flex-end;
    background: linear-gradient(135deg, var(--gold) 0%, var(--gold-dark) 100%);
    color: #000;
    border-bottom-right-radius: 4px;
    box-shadow: 0 4px 15px rgba(212, 175, 55, 0.3);
  }

  .message.user .message-content {
    padding: 12px 16px;
    font-size: 1rem;
    line-height: 1.6;
  }

  .message.assistant {
    align-self: flex-start;
    background: #2a2a2a;
    color: var(--text-primary);
    border-bottom-left-radius: 4px;
    border: 1px solid rgba(212, 175, 55, 0.35);
    box-shadow: 0 6px 18px rgba(0,0,0,0.28);
    max-width: 100%;
  }

  .message.assistant .message-content {
    padding: 18px 16px 14px;
    overflow-x: auto;
    font-size: 1rem;
    line-height: 1.75;
  }

  .message.assistant h1,
  .message.assistant h2,
  .message.assistant h3 {
    margin: 0 0 12px 0;
    color: var(--gold-light);
    font-weight: 700;
    line-height: 1.3;
  }

  .message.assistant h1 {
    font-size: 1.55rem;
    border-bottom: 1px solid rgba(212,175,55,0.35);
    padding-bottom: 8px;
    margin-bottom: 14px;
  }

  .message.assistant h2 {
    font-size: 1.28rem;
    margin-top: 18px;
  }

  .message.assistant h3 {
    font-size: 1.12rem;
    color: var(--gold);
    margin-top: 16px;
  }

  .message.assistant p {
    margin: 0 0 14px 0;
    font-size: 1rem;
    color: #f1f1f1;
  }

  .message.assistant p:last-child {
    margin-bottom: 0;
  }

  .message.assistant ul,
  .message.assistant ol {
    margin: 10px 0 16px 0;
    padding-left: 22px;
  }

  .message.assistant li {
    margin: 8px 0;
    font-size: 0.98rem;
    color: #f3f3f3;
  }

  .message.assistant ul li::marker {
    color: var(--gold);
  }

  .message.assistant blockquote {
    margin: 14px 0;
    padding: 12px 14px;
    background: rgba(212, 175, 55, 0.08);
    border-left: 4px solid var(--gold);
    border-radius: 0 10px 10px 0;
    font-style: italic;
    color: #dddddd;
  }

  .message.assistant code {
    background: rgba(212, 175, 55, 0.12);
    color: var(--gold-light);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.9em;
  }

  .message.assistant pre {
    background: #111;
    border: 1px solid rgba(212, 175, 55, 0.2);
    border-radius: 8px;
    padding: 12px;
    overflow-x: auto;
    margin: 12px 0;
    color: #f1f1f1;
  }

  .message.assistant strong {
    color: var(--gold-light);
    font-weight: 700;
  }

  .message.assistant em {
    color: var(--gold);
    font-style: italic;
  }

  .message.assistant a {
    color: #5d8cff;
    text-decoration: underline;
    text-underline-offset: 2px;
    transition: color 0.2s;
    font-weight: 500;
  }

  .message.assistant a:hover {
    color: #82a8ff;
  }

  .message.assistant .table-container {
    overflow-x: auto;
    margin: 14px 0;
    border-radius: 10px;
    border: 1px solid rgba(212,175,55,0.3);
    background: #111;
  }

  .message.assistant table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
    background: #111;
    min-width: 520px;
  }

  .message.assistant th {
    background: #2f2a18;
    color: var(--gold-light);
    font-weight: 700;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid var(--gold);
    white-space: nowrap;
  }

  .message.assistant td {
    padding: 12px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    color: #f3f3f3;
    vertical-align: top;
  }

  .message.assistant tr:hover td {
    background: rgba(212, 175, 55, 0.04);
  }

  .message-time {
    font-size: 0.78rem;
    margin-top: 6px;
    text-align: right;
    opacity: 0.75;
    padding: 0 16px 10px 16px;
  }

  .message.user .message-time {
    color: #000000 !important;
  }

  .message.assistant .message-time {
    color: #cccccc !important;
    text-align: left;
    padding-left: 16px;
  }

  .feedback-buttons {
    display: flex;
    gap: 8px;
    padding: 0 16px 16px 16px;
    flex-wrap: wrap;
  }

  .feedback-btn {
    background: rgba(212, 175, 55, 0.1);
    border: 1px solid rgba(212, 175, 55, 0.3);
    border-radius: 20px;
    color: var(--gold);
    padding: 6px 14px;
    font-size: 0.86rem;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .feedback-btn:hover {
    background: var(--gold);
    color: #000;
    border-color: var(--gold);
  }

  .feedback-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .assistant-suggestions {
    padding: 12px;
    border-top: var(--border-gold);
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    background: var(--bg-dark);
    max-height: 80px;
    overflow-y: auto;
    display: none;
  }

  .quick-actions {
    padding: 0 12px 12px;
    border-top: var(--border-gold);
    background: var(--bg-dark);
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .quick-actions .btn {
    padding: 8px 14px;
    font-size: 0.82rem;
    background: rgba(212,175,55,0.1);
    border: 1px solid rgba(212,175,55,0.3);
    color: var(--text-primary);
    border-radius: 30px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .quick-actions .btn:hover {
    background: var(--gold);
    color: #000;
  }

  .back-to-bottom {
    position: absolute;
    bottom: 100px;
    right: 20px;
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #D4AF37;
    color: #000;
    border: 2px solid #D4AF37;
    box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    cursor: pointer;
    display: none;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    transition: all 0.3s ease;
    z-index: 10001;
  }

  .back-to-bottom:hover {
    transform: scale(1.1);
    background: #000;
    color: #D4AF37;
  }

  .back-to-bottom.visible {
    display: flex;
  }

  .assistant-input-area {
    padding: 12px 16px;
    border-top: var(--border-gold);
    display: flex;
    gap: 10px;
    background: #151515;
    flex-wrap: wrap;
  }

  .assistant-input-area input {
    flex: 1;
    min-width: 200px;
    padding: 14px 18px;
    border-radius: 28px;
    border: var(--border-gold);
    background: #101010;
    color: var(--text-primary);
    font-family: inherit;
    font-size: 1rem;
    transition: all 0.2s;
  }

  .assistant-input-area input:focus {
    outline: none;
    border-color: var(--gold);
    box-shadow: 0 0 0 2px rgba(212, 175, 55, 0.2);
  }

  .assistant-input-area input::placeholder {
    color: var(--text-secondary);
  }

  .assistant-input-area button {
    padding: 14px 24px;
    border-radius: 28px;
    border: none;
    background: linear-gradient(135deg, var(--gold), var(--gold-dark));
    color: #000;
    font-weight: 700;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
    box-shadow: 0 4px 12px rgba(212, 175, 55, 0.3);
  }

  .assistant-input-area button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(212, 175, 55, 0.4);
  }

  .assistant-input-area button:active {
    transform: translateY(0);
  }

  .typing-indicator {
    display: flex;
    gap: 4px;
    padding: 12px 16px;
    background: var(--bg-elevated);
    border-radius: 16px;
    align-self: flex-start;
    border-bottom-left-radius: 4px;
    border: var(--border-gold);
    width: fit-content;
    margin-bottom: 4px;
  }

  .typing-indicator span {
    width: 8px;
    height: 8px;
    background: var(--gold);
    border-radius: 50%;
    animation: typing-bounce 1.4s infinite ease-in-out both;
  }

  .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
  .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

  @keyframes typing-bounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
    40% { transform: scale(1); opacity: 1; }
  }

  @media (max-width: 768px) {
    .assistant-header-info h3 {
      font-size: 1rem;
    }

    .assistant-avatar {
      width: 36px;
      height: 36px;
      font-size: 20px;
    }

    .assistant-close {
      font-size: 1.8rem;
      width: 40px;
      height: 40px;
    }

    .assistant-messages {
      padding: 14px 10px 12px;
    }

    .message {
      max-width: 96%;
    }

    .message.assistant .message-content {
      padding: 16px 14px 12px;
      font-size: 0.96rem;
      line-height: 1.65;
    }

    .message.assistant h1 {
      font-size: 1.35rem;
    }

    .message.assistant h2 {
      font-size: 1.16rem;
    }

    .message.assistant h3 {
      font-size: 1.02rem;
    }

    .message.assistant table {
      font-size: 0.82rem;
      min-width: 460px;
    }

    .assistant-input-area {
      padding: 12px;
      gap: 10px;
    }

    .assistant-input-area button {
      padding: 13px 20px;
      font-size: 0.95rem;
    }

    .feedback-buttons {
      gap: 10px;
    }

    .feedback-btn {
      font-size: 0.84rem;
      padding: 7px 12px;
    }
  }
  `;
  document.head.appendChild(style);

  // ============================================================
  // INTERFACE UTILISATEUR
  // ============================================================

  const button = document.createElement('div');
  button.className = 'assistant-button';
  button.innerHTML = '<img src="https://img.icons8.com/ios-filled/50/ffffff/chat.png" alt="assistant">';
  button.title = "Mr XPRONOS Assistant";
  document.body.appendChild(button);

  const windowDiv = document.createElement('div');
  windowDiv.className = 'assistant-window';
  windowDiv.innerHTML = `
    <div class="assistant-header">
      <div class="assistant-header-left">
        <div class="assistant-avatar">🎯</div>
        <div class="assistant-header-info">
          <h3>Mr XPRONOS</h3>
          <div class="assistant-status">
            <span class="status-dot"></span>
            <span>En ligne</span>
          </div>
        </div>
      </div>
      <div>
        <button class="clear-cache" title="Vider le cache des réponses">🗑️</button>
        <button class="assistant-close">&times;</button>
      </div>
    </div>
    <div class="assistant-messages" id="assistant-messages"></div>
    <button class="back-to-bottom" id="back-to-bottom" aria-label="Aller en bas"><i class="fas fa-arrow-down"></i></button>
    <div class="assistant-suggestions" id="assistant-suggestions" style="display: none;"></div>
    <div class="quick-actions" id="quick-actions"></div>
    <div class="assistant-input-area">
      <input type="text" id="assistant-input" placeholder="Posez votre question...">
      <button id="assistant-send">Envoyer</button>
    </div>
  `;
  document.body.appendChild(windowDiv);

  const messagesDiv = document.getElementById('assistant-messages');
  const input = document.getElementById('assistant-input');
  const sendBtn = document.getElementById('assistant-send');
  const closeBtn = document.querySelector('.assistant-close');
  const clearCacheBtn = document.querySelector('.clear-cache');
  const suggestionsDiv = document.getElementById('assistant-suggestions');
  const quickActionsDiv = document.getElementById('quick-actions');
  const bottomBtn = document.getElementById('back-to-bottom');

  // ============================================================
  // HELPERS
  // ============================================================

  function getCurrentTime() {
    return new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  function saveCache() {
    try {
      const toStore = JSON.stringify(Array.from(responseCache.entries()));
      localStorage.setItem('assistant_response_cache', toStore);
    } catch (e) {
      console.warn('Erreur sauvegarde cache', e);
    }
  }

  function addToCache(question, answer) {
    responseCache.set(question, {
      answer,
      timestamp: Date.now()
    });

    if (responseCache.size > 100) {
      const oldestKey = responseCache.keys().next().value;
      responseCache.delete(oldestKey);
    }
    saveCache();
  }

  function getFromCache(question) {
    const cached = responseCache.get(question);
    if (!cached) return null;

    if (Date.now() - cached.timestamp > CACHE_TTL) {
      responseCache.delete(question);
      saveCache();
      return null;
    }

    return cached.answer;
  }

  function isNoPronoMessage(answer) {
    return answer.includes('Aucun pronostic disponible');
  }

  function cleanAssistantHtmlResponse(html) {
    if (!html) return '';

    let cleaned = String(html).trim();
    cleaned = cleaned.replace(/^```html\s*/i, '');
    cleaned = cleaned.replace(/^```\s*/i, '');
    cleaned = cleaned.replace(/\s*```$/i, '');
    cleaned = cleaned.replace(/^`+|`+$/g, '').trim();

    // enlève aussi les balises parasites de début/fin parfois générées
    cleaned = cleaned.replace(/^<p>\s*```html\s*<\/p>/i, '');
    cleaned = cleaned.replace(/<p>\s*```\s*<\/p>$/i, '');

    return cleaned.trim();
  }

  function wrapTablesInContainer(html) {
    if (!html) return '';
    return html.replace(/<table([\s\S]*?)<\/table>/gi, function(match) {
      if (match.includes('table-container')) return match;
      return `<div class="table-container">${match}</div>`;
    });
  }

  let typingIndicator = null;

  function showTyping() {
    if (typingIndicator) return;
    typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.innerHTML = '<span></span><span></span><span></span>';
    messagesDiv.appendChild(typingIndicator);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  }

  function hideTyping() {
    if (typingIndicator) {
      typingIndicator.remove();
      typingIndicator = null;
    }
  }

  // ============================================================
  // PERSISTANCE DES MESSAGES
  // ============================================================
  function loadMessages() {
    try {
      const saved = localStorage.getItem(MESSAGES_STORAGE_KEY);
      if (saved) {
        const messages = JSON.parse(saved);
        messages.forEach(msg => {
          addMessage(msg.text, msg.sender, msg.isHTML, msg.conversationId, false);
        });
      } else {
        addMessage(
          `<p>👋 <strong>Bonjour !</strong> Je suis votre assistant personnel pour les paris sportifs.</p>
          <p>Je peux vous aider avec :</p>
          <ul>
            <li>Les pronostics du jour 📊</li>
            <li>Les bonus bookmakers 🎁</li>
            <li>Le <strong>LIVE VIP</strong> 🔴</li>
            <li>Vos questions sur le site 🛟</li>
          </ul>
          <p>Tous les montants sont indiqués en <strong>Francs CFA</strong>.</p>`,
          'assistant',
          true,
          null,
          false
        );
      }
    } catch (e) {
      console.warn('Erreur chargement des messages', e);
    }
  }

  function saveMessages() {
    const messages = [];
    const msgElements = messagesDiv.querySelectorAll('.message');

    msgElements.forEach(el => {
      const sender = el.classList.contains('user') ? 'user' : 'assistant';
      const contentEl = el.querySelector('.message-content');
      const isHTML = sender === 'assistant';
      const text = isHTML ? contentEl.innerHTML : contentEl.textContent;
      const convId = el.dataset.conversationId || null;
      messages.push({ text, sender, isHTML, conversationId: convId });
    });

    const toStore = messages.slice(-20);
    try {
      localStorage.setItem(MESSAGES_STORAGE_KEY, JSON.stringify(toStore));
    } catch (e) {
      console.warn('Erreur sauvegarde des messages', e);
    }
  }

  function addMessage(text, sender, isHTML = false, conversationId = null, save = true) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    if (conversationId) {
      msgDiv.dataset.conversationId = conversationId;
    }

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (isHTML || sender === 'assistant') {
      const cleaned = wrapTablesInContainer(cleanAssistantHtmlResponse(text));
      contentDiv.innerHTML = cleaned;
    } else {
      contentDiv.textContent = text;
    }

    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = getCurrentTime();

    msgDiv.appendChild(contentDiv);
    msgDiv.appendChild(timeDiv);

    if (sender === 'assistant' && conversationId) {
      const feedbackDiv = document.createElement('div');
      feedbackDiv.className = 'feedback-buttons';
      feedbackDiv.innerHTML = `
        <button class="feedback-btn like" data-id="${conversationId}">👍 Utile</button>
        <button class="feedback-btn dislike" data-id="${conversationId}">👎 Pas utile</button>
      `;

      msgDiv.appendChild(feedbackDiv);

      feedbackDiv.querySelectorAll('.feedback-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const isLike = btn.classList.contains('like');
          const convId = btn.dataset.id;

          try {
            const response = await fetch(API_BASE, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                action: 'feedback',
                conversation_id: convId,
                user_id: userId,
                feedback: isLike
              })
            });

            if (response.ok) {
              btn.disabled = true;
              btn.textContent = isLike ? '👍 Merci' : '👎 Merci';
            }
          } catch (error) {
            console.error('Erreur feedback:', error);
          }
        });
      });
    }

    messagesDiv.appendChild(msgDiv);

    setTimeout(() => {
      messagesDiv.scrollTo({
        top: messagesDiv.scrollHeight,
        behavior: 'smooth'
      });
    }, 100);

    if (save) {
      saveMessages();
    }
  }

  // ============================================================
  // SCROLL
  // ============================================================
  messagesDiv.addEventListener('scroll', () => {
    const isAtBottom = messagesDiv.scrollHeight - messagesDiv.scrollTop - messagesDiv.clientHeight < 50;
    if (isAtBottom) {
      bottomBtn.classList.remove('visible');
    } else {
      bottomBtn.classList.add('visible');
    }
  });

  bottomBtn.addEventListener('click', () => {
    messagesDiv.scrollTo({
      top: messagesDiv.scrollHeight,
      behavior: 'smooth'
    });
  });

  // ============================================================
  // SUGGESTIONS / ACTIONS
  // ============================================================
  async function fetchSuggestions() {
    return [];
  }

  async function renderSuggestions() {
    suggestionsDiv.innerHTML = '';
  }

  function renderQuickActions() {
    quickActionsDiv.innerHTML = '';

    const actions = [
      { label: '📊 Pronostics du jour', value: 'Quels sont les pronostics du jour ?' },
      { label: '🎁 Bonus 1xBet', value: 'Quel est le bonus 1xBet avec XPVIP ?' },
      { label: '🎬 LIVE VIP', value: 'Comment accéder au LIVE VIP ?' },
      { label: '📞 Support', value: 'Comment contacter le support ?' }
    ];

    actions.forEach(a => {
      const btn = document.createElement('button');
      btn.className = 'btn';
      btn.textContent = a.label;
      btn.addEventListener('click', () => {
        input.value = a.value;
        sendMessage();
      });
      quickActionsDiv.appendChild(btn);
    });
  }

  function buildHistoryPayload() {
    const messages = [];
    const msgElements = messagesDiv.querySelectorAll('.message');
    const recent = Array.from(msgElements).slice(-10);

    recent.forEach(el => {
      const role = el.classList.contains('user') ? 'user' : 'assistant';
      const contentEl = el.querySelector('.message-content');
      const contenu = role === 'assistant' ? contentEl.innerHTML : contentEl.textContent;
      messages.push({ role, contenu });
    });

    return messages;
  }

  // ============================================================
  // ENVOI MESSAGE
  // ============================================================
  async function sendMessage() {
    const question = input.value.trim();
    if (!question) return;

    addMessage(question, 'user', false, null, true);
    input.value = '';
    showTyping();

    const historique = buildHistoryPayload();
    const cachedAnswer = getFromCache(question);
    const useCache = historique.length === 0 && cachedAnswer && !isNoPronoMessage(cachedAnswer);

    if (useCache) {
      hideTyping();
      addMessage(cachedAnswer, 'assistant', true, null, true);
      return;
    }

    try {
      const response = await fetch(API_BASE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          question,
          user_id: userId,
          historique: historique
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Erreur ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      hideTyping();

      const cleanedAnswer = cleanAssistantHtmlResponse(data.answer);

      if (historique.length === 0 && !isNoPronoMessage(cleanedAnswer)) {
        addToCache(question, cleanedAnswer);
      }

      addMessage(cleanedAnswer, 'assistant', true, data.conversation_id, true);

    } catch (error) {
      hideTyping();
      addMessage(
        `<p><strong>Oups !</strong> Une erreur est survenue. Veuillez réessayer plus tard.</p>
         <p><em>Erreur technique : ${String(error.message || error)}</em></p>`,
        'assistant',
        true,
        null,
        true
      );
      console.error('Assistant Error:', error);
    }
  }

  // ============================================================
  // ÉVÉNEMENTS
  // ============================================================
  button.addEventListener('click', () => {
    isOpen = !isOpen;
    windowDiv.classList.toggle('open', isOpen);

    if (isOpen) {
      document.body.classList.add('assistant-open');
      button.classList.add('hidden');
      input.focus();
      renderSuggestions();
      renderQuickActions();

      setTimeout(() => {
        messagesDiv.dispatchEvent(new Event('scroll'));
      }, 100);
    } else {
      document.body.classList.remove('assistant-open');
      button.classList.remove('hidden');
    }
  });

  closeBtn.addEventListener('click', () => {
    isOpen = false;
    windowDiv.classList.remove('open');
    document.body.classList.remove('assistant-open');
    button.classList.remove('hidden');
  });

  clearCacheBtn.addEventListener('click', () => {
    if (confirm('Vider le cache des réponses de l\'assistant ?')) {
      responseCache.clear();
      saveCache();
      alert('Cache vidé.');
    }
  });

  sendBtn.addEventListener('click', sendMessage);

  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen) {
      isOpen = false;
      windowDiv.classList.remove('open');
      document.body.classList.remove('assistant-open');
      button.classList.remove('hidden');
    }
  });

  loadMessages();

  console.log('✅ Mr XPRONOS Assistant chargé avec succès');
})();