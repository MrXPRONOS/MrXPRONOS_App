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
  const DYNAMIC_QUESTION = /\b(aujourd.?hui|demain|hier|live|direct|score|résultat|resultat|prono|pronostic|match|cote|signal|vip|bonus|promo|prix|tarif|disponible)\b/i;
  let requestInFlight = false;

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
  style.textContent = "\n:root {\n  --mx-ai-gold: #d7b45a;\n  --mx-ai-gold-strong: #f0ce76;\n  --mx-ai-navy: #070b13;\n  --mx-ai-panel: #0b111c;\n  --mx-ai-panel-2: #111927;\n  --mx-ai-line: rgba(215,180,90,.22);\n  --mx-ai-line-strong: rgba(215,180,90,.48);\n  --mx-ai-text: #f7f8fb;\n  --mx-ai-muted: #929baa;\n  --mx-ai-green: #29c36a;\n  --mx-ai-red: #ef5350;\n  --mx-ai-blue: #7ba5ff;\n}\n\n.assistant-button,\n.assistant-window,\n.assistant-window * {\n  box-sizing: border-box;\n}\n\nbody.assistant-open {\n  overflow: hidden;\n}\n\n.assistant-button {\n  position: fixed;\n  right: 24px;\n  bottom: 24px;\n  min-width: 166px;\n  height: 58px;\n  padding: 8px 14px 8px 9px;\n  border-radius: 18px;\n  border: 1px solid rgba(240,206,118,.58);\n  background:\n    linear-gradient(135deg, rgba(240,206,118,.18), transparent 42%),\n    linear-gradient(145deg, #141923 0%, #090d14 100%);\n  color: var(--mx-ai-text);\n  box-shadow: 0 16px 40px rgba(0,0,0,.46), 0 0 0 1px rgba(255,255,255,.035) inset;\n  cursor: pointer;\n  z-index: 2147483001;\n  display: flex;\n  align-items: center;\n  gap: 10px;\n  font-family: 'Montserrat', system-ui, sans-serif;\n  transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;\n  isolation: isolate;\n}\n\n.assistant-button::before {\n  content: \"\";\n  position: absolute;\n  inset: -1px;\n  border-radius: inherit;\n  background: linear-gradient(110deg, rgba(240,206,118,.48), transparent 32%, transparent 68%, rgba(215,180,90,.2));\n  z-index: -1;\n  opacity: .45;\n  pointer-events: none;\n}\n\n.assistant-button:hover {\n  transform: translateY(-3px);\n  border-color: rgba(240,206,118,.86);\n  box-shadow: 0 20px 48px rgba(0,0,0,.5), 0 0 24px rgba(215,180,90,.14);\n}\n\n.assistant-button:active {\n  transform: translateY(-1px) scale(.985);\n}\n\n.assistant-button.hidden {\n  display: none !important;\n}\n\n.assistant-button-mark {\n  width: 40px;\n  height: 40px;\n  flex: 0 0 40px;\n  border-radius: 13px;\n  display: grid;\n  place-items: center;\n  background: linear-gradient(145deg, #f2d27e, #b88e30);\n  box-shadow: 0 6px 18px rgba(215,180,90,.24);\n  overflow: hidden;\n}\n\n.assistant-button-mark img {\n  width: 31px;\n  height: 31px;\n  object-fit: contain;\n}\n\n.assistant-button-copy {\n  min-width: 0;\n  text-align: left;\n  line-height: 1.05;\n}\n\n.assistant-button-copy strong {\n  display: block;\n  color: #fff;\n  font-size: .84rem;\n  font-weight: 800;\n  letter-spacing: .02em;\n}\n\n.assistant-button-copy small {\n  display: block;\n  margin-top: 4px;\n  color: var(--mx-ai-muted);\n  font-size: .66rem;\n  font-weight: 600;\n  white-space: nowrap;\n}\n\n.assistant-button-status {\n  width: 8px;\n  height: 8px;\n  margin-left: auto;\n  border-radius: 50%;\n  background: var(--mx-ai-green);\n  box-shadow: 0 0 0 3px rgba(41,195,106,.12), 0 0 12px rgba(41,195,106,.4);\n}\n\n.assistant-window {\n  position: fixed;\n  right: 24px;\n  bottom: 24px;\n  width: min(540px, calc(100vw - 48px));\n  height: min(760px, calc(100dvh - 48px));\n  min-height: 520px;\n  z-index: 2147483000;\n  display: none;\n  flex-direction: column;\n  overflow: hidden;\n  color: var(--mx-ai-text);\n  font-family: 'Montserrat', system-ui, sans-serif;\n  border-radius: 26px;\n  border: 1px solid rgba(215,180,90,.32);\n  background:\n    radial-gradient(circle at 88% -8%, rgba(215,180,90,.12), transparent 28%),\n    linear-gradient(180deg, #0b111b 0%, #070b12 100%);\n  box-shadow: 0 30px 90px rgba(0,0,0,.66), 0 0 0 1px rgba(255,255,255,.025) inset;\n  transform-origin: right bottom;\n}\n\n.assistant-window.open {\n  display: flex;\n  animation: mx-assistant-open .22s ease-out both;\n}\n\n@keyframes mx-assistant-open {\n  from { opacity: 0; transform: translateY(12px) scale(.985); }\n  to { opacity: 1; transform: translateY(0) scale(1); }\n}\n\n.assistant-header {\n  min-height: 76px;\n  padding: 12px 14px 11px;\n  border-bottom: 1px solid var(--mx-ai-line);\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  gap: 12px;\n  background: rgba(8,13,22,.92);\n  backdrop-filter: blur(18px);\n  flex: 0 0 auto;\n}\n\n.assistant-header-left {\n  min-width: 0;\n  display: flex;\n  align-items: center;\n  gap: 11px;\n}\n\n.assistant-avatar {\n  position: relative;\n  width: 46px;\n  height: 46px;\n  flex: 0 0 46px;\n  border-radius: 15px;\n  display: grid;\n  place-items: center;\n  overflow: hidden;\n  background: linear-gradient(145deg, #f1cf78, #b2872d);\n  box-shadow: 0 8px 24px rgba(215,180,90,.18);\n}\n\n.assistant-avatar img {\n  width: 36px;\n  height: 36px;\n  object-fit: contain;\n}\n\n.assistant-header-info {\n  min-width: 0;\n}\n\n.assistant-kicker {\n  display: block;\n  margin-bottom: 2px;\n  color: var(--mx-ai-gold);\n  font-size: .61rem;\n  font-weight: 800;\n  letter-spacing: .16em;\n  text-transform: uppercase;\n}\n\n.assistant-header-info h3 {\n  margin: 0;\n  color: #fff;\n  font-size: 1rem;\n  font-weight: 800;\n  line-height: 1.16;\n  white-space: nowrap;\n  overflow: hidden;\n  text-overflow: ellipsis;\n}\n\n.assistant-status {\n  margin-top: 4px;\n  display: flex;\n  align-items: center;\n  gap: 6px;\n  color: var(--mx-ai-muted);\n  font-size: .69rem;\n  font-weight: 600;\n}\n\n.status-dot {\n  width: 7px;\n  height: 7px;\n  flex: 0 0 7px;\n  border-radius: 50%;\n  background: var(--mx-ai-green);\n  box-shadow: 0 0 8px rgba(41,195,106,.42);\n}\n\n.assistant-header-actions {\n  display: flex;\n  align-items: center;\n  gap: 6px;\n}\n\n.clear-cache,\n.assistant-close {\n  width: 38px;\n  height: 38px;\n  padding: 0;\n  border-radius: 12px;\n  border: 1px solid rgba(255,255,255,.08);\n  background: rgba(255,255,255,.035);\n  color: #c9ced7;\n  display: grid;\n  place-items: center;\n  cursor: pointer;\n  transition: background .18s ease, border-color .18s ease, color .18s ease, transform .18s ease;\n}\n\n.clear-cache {\n  font-size: 1rem;\n}\n\n.assistant-close {\n  font-size: 1.55rem;\n  line-height: 1;\n}\n\n.clear-cache:hover,\n.assistant-close:hover {\n  color: var(--mx-ai-gold-strong);\n  border-color: rgba(215,180,90,.34);\n  background: rgba(215,180,90,.08);\n  transform: translateY(-1px);\n}\n\n.assistant-messages {\n  flex: 1 1 auto;\n  min-height: 0;\n  overflow-y: auto;\n  padding: 18px 18px 16px;\n  display: flex;\n  flex-direction: column;\n  gap: 12px;\n  scroll-behavior: smooth;\n  position: relative;\n  background:\n    radial-gradient(circle at 18% 0%, rgba(77,104,146,.08), transparent 34%),\n    linear-gradient(180deg, rgba(12,18,29,.84), rgba(7,11,18,.96));\n}\n\n.assistant-messages::-webkit-scrollbar {\n  width: 5px;\n}\n\n.assistant-messages::-webkit-scrollbar-track {\n  background: transparent;\n}\n\n.assistant-messages::-webkit-scrollbar-thumb {\n  background: rgba(215,180,90,.38);\n  border-radius: 999px;\n}\n\n.message {\n  max-width: 88%;\n  border-radius: 17px;\n  word-wrap: break-word;\n  overflow-wrap: anywhere;\n  font-size: .9rem;\n  line-height: 1.55;\n  animation: message-appear .22s ease-out;\n}\n\n@keyframes message-appear {\n  from { opacity: 0; transform: translateY(7px); }\n  to { opacity: 1; transform: translateY(0); }\n}\n\n.message.user {\n  align-self: flex-end;\n  max-width: 79%;\n  color: #111;\n  background: linear-gradient(135deg, #efd27d 0%, #c69d41 100%);\n  border: 1px solid rgba(255,238,184,.46);\n  border-bottom-right-radius: 6px;\n  box-shadow: 0 8px 22px rgba(0,0,0,.18);\n}\n\n.message.assistant {\n  align-self: flex-start;\n  max-width: 92%;\n  color: var(--mx-ai-text);\n  background: linear-gradient(145deg, rgba(22,31,46,.96), rgba(14,21,33,.96));\n  border: 1px solid rgba(255,255,255,.07);\n  border-left: 2px solid rgba(215,180,90,.62);\n  border-bottom-left-radius: 6px;\n  box-shadow: 0 10px 28px rgba(0,0,0,.22);\n}\n\n.message.user .message-content {\n  padding: 10px 13px 8px;\n  font-size: .9rem;\n  line-height: 1.48;\n  font-weight: 600;\n}\n\n.message.assistant .message-content {\n  padding: 13px 14px 9px;\n  overflow-x: auto;\n  font-size: .89rem;\n  line-height: 1.62;\n}\n\n.message.assistant h1,\n.message.assistant h2,\n.message.assistant h3,\n.message.assistant h4 {\n  margin: 0 0 8px;\n  color: var(--mx-ai-gold-strong);\n  font-weight: 800;\n  line-height: 1.28;\n}\n\n.message.assistant h1 { font-size: 1.18rem; }\n.message.assistant h2 { font-size: 1.08rem; margin-top: 13px; }\n.message.assistant h3 { font-size: .98rem; margin-top: 11px; }\n.message.assistant h4 { font-size: .92rem; margin-top: 10px; }\n\n.message.assistant p {\n  margin: 0 0 9px;\n  color: #e9edf3;\n  font-size: .89rem;\n}\n\n.message.assistant p:last-child {\n  margin-bottom: 0;\n}\n\n.message.assistant ul,\n.message.assistant ol {\n  margin: 7px 0 10px;\n  padding-left: 19px;\n}\n\n.message.assistant li {\n  margin: 4px 0;\n  color: #e8ebf1;\n  font-size: .87rem;\n}\n\n.message.assistant li::marker {\n  color: var(--mx-ai-gold);\n}\n\n.message.assistant blockquote {\n  margin: 10px 0;\n  padding: 9px 11px;\n  color: #d8dde5;\n  background: rgba(215,180,90,.065);\n  border-left: 3px solid var(--mx-ai-gold);\n  border-radius: 0 9px 9px 0;\n}\n\n.message.assistant strong {\n  color: #f5d884;\n  font-weight: 800;\n}\n\n.message.assistant em {\n  color: #d8bf7d;\n}\n\n.message.assistant a {\n  color: var(--mx-ai-blue);\n  text-decoration: none;\n  border-bottom: 1px solid rgba(123,165,255,.42);\n  font-weight: 650;\n}\n\n.message.assistant a:hover {\n  color: #a7c1ff;\n}\n\n.message.assistant code {\n  padding: 2px 5px;\n  border-radius: 5px;\n  color: #f5d884;\n  background: rgba(215,180,90,.1);\n  font-size: .86em;\n}\n\n.message.assistant pre {\n  margin: 9px 0;\n  padding: 10px;\n  overflow-x: auto;\n  border-radius: 10px;\n  border: 1px solid rgba(215,180,90,.16);\n  background: #070a10;\n  color: #eef1f5;\n}\n\n.message.assistant .table-container {\n  margin: 10px 0;\n  overflow-x: auto;\n  border-radius: 10px;\n  border: 1px solid rgba(215,180,90,.2);\n  background: #080c13;\n}\n\n.message.assistant table {\n  width: 100%;\n  min-width: 480px;\n  border-collapse: collapse;\n  background: transparent;\n  font-size: .79rem;\n}\n\n.message.assistant th {\n  padding: 9px 10px;\n  color: var(--mx-ai-gold-strong);\n  text-align: left;\n  white-space: nowrap;\n  background: rgba(215,180,90,.08);\n  border-bottom: 1px solid rgba(215,180,90,.22);\n}\n\n.message.assistant td {\n  padding: 9px 10px;\n  color: #e7ebf0;\n  vertical-align: top;\n  border-bottom: 1px solid rgba(255,255,255,.05);\n}\n\n.message-time {\n  padding: 0 13px 8px;\n  margin: 0;\n  font-size: .62rem;\n  opacity: .62;\n  text-align: right;\n}\n\n.message.user .message-time {\n  color: rgba(0,0,0,.66) !important;\n}\n\n.message.assistant .message-time {\n  padding-left: 14px;\n  color: #9ba3af !important;\n  text-align: left;\n}\n\n.feedback-buttons {\n  padding: 0 12px 11px 12px;\n  display: flex;\n  flex-wrap: wrap;\n  gap: 6px;\n}\n\n.feedback-btn {\n  min-height: 28px;\n  padding: 5px 9px;\n  border-radius: 9px;\n  border: 1px solid rgba(215,180,90,.2);\n  color: #cfd4dd;\n  background: rgba(215,180,90,.055);\n  font-size: .7rem;\n  font-weight: 650;\n  cursor: pointer;\n  transition: all .18s ease;\n}\n\n.feedback-btn:hover {\n  color: #141414;\n  border-color: var(--mx-ai-gold);\n  background: var(--mx-ai-gold);\n}\n\n.feedback-btn:disabled {\n  opacity: .45;\n  cursor: default;\n}\n\n.assistant-suggestions {\n  display: none !important;\n}\n\n.quick-actions {\n  flex: 0 0 auto;\n  padding: 9px 12px 7px;\n  display: flex;\n  flex-wrap: wrap;\n  gap: 6px;\n  border-top: 1px solid rgba(215,180,90,.13);\n  background: rgba(8,13,21,.96);\n}\n\n.quick-actions .btn {\n  min-height: 32px;\n  padding: 6px 10px;\n  border-radius: 10px;\n  border: 1px solid rgba(215,180,90,.19);\n  color: #dfe3e9;\n  background: rgba(255,255,255,.025);\n  font-family: inherit;\n  font-size: .72rem;\n  font-weight: 650;\n  cursor: pointer;\n  transition: all .18s ease;\n}\n\n.quick-actions .btn:hover {\n  color: #17130a;\n  border-color: var(--mx-ai-gold);\n  background: var(--mx-ai-gold);\n}\n\n.assistant-input-area {\n  flex: 0 0 auto;\n  padding: 9px 11px 11px;\n  display: flex;\n  align-items: center;\n  gap: 8px;\n  border-top: 1px solid rgba(255,255,255,.055);\n  background: #080d15;\n}\n\n.assistant-input-area input {\n  flex: 1 1 auto;\n  min-width: 0;\n  height: 44px;\n  padding: 0 15px;\n  border-radius: 14px;\n  border: 1px solid rgba(255,255,255,.09);\n  outline: none;\n  color: #f5f7fa;\n  background: rgba(255,255,255,.035);\n  font-family: inherit;\n  font-size: .86rem;\n  transition: border-color .18s ease, box-shadow .18s ease, background .18s ease;\n}\n\n.assistant-input-area input::placeholder {\n  color: #717b89;\n}\n\n.assistant-input-area input:focus {\n  border-color: rgba(215,180,90,.62);\n  background: rgba(255,255,255,.045);\n  box-shadow: 0 0 0 3px rgba(215,180,90,.08);\n}\n\n.assistant-input-area button {\n  flex: 0 0 auto;\n  height: 44px;\n  min-width: 92px;\n  padding: 0 15px;\n  border: 0;\n  border-radius: 14px;\n  color: #18130a;\n  background: linear-gradient(135deg, #efd27d, #c79b3e);\n  box-shadow: 0 7px 20px rgba(215,180,90,.17);\n  font-family: inherit;\n  font-size: .79rem;\n  font-weight: 850;\n  cursor: pointer;\n  transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;\n}\n\n.assistant-input-area button:hover {\n  transform: translateY(-1px);\n  filter: brightness(1.035);\n  box-shadow: 0 9px 24px rgba(215,180,90,.23);\n}\n\n.assistant-input-area button:active {\n  transform: translateY(0);\n}\n\n.typing-indicator {\n  width: fit-content;\n  padding: 10px 12px;\n  display: flex;\n  align-items: center;\n  gap: 5px;\n  align-self: flex-start;\n  border-radius: 14px 14px 14px 5px;\n  border: 1px solid rgba(215,180,90,.18);\n  background: rgba(18,26,39,.96);\n}\n\n.typing-indicator span {\n  width: 6px;\n  height: 6px;\n  border-radius: 50%;\n  background: var(--mx-ai-gold);\n  animation: typing-bounce 1.25s infinite ease-in-out both;\n}\n\n.typing-indicator span:nth-child(1) { animation-delay: -.28s; }\n.typing-indicator span:nth-child(2) { animation-delay: -.14s; }\n\n@keyframes typing-bounce {\n  0%, 80%, 100% { transform: translateY(0); opacity: .38; }\n  40% { transform: translateY(-3px); opacity: 1; }\n}\n\n.back-to-bottom {\n  position: absolute;\n  right: 15px;\n  bottom: 118px;\n  width: 36px;\n  height: 36px;\n  padding: 0;\n  border-radius: 12px;\n  border: 1px solid rgba(215,180,90,.42);\n  color: #15120a;\n  background: linear-gradient(145deg, #ead07f, #ba9137);\n  box-shadow: 0 10px 22px rgba(0,0,0,.32);\n  cursor: pointer;\n  display: none;\n  place-items: center;\n  z-index: 2147483002;\n  font-size: 1rem;\n  font-weight: 900;\n}\n\n.back-to-bottom.visible {\n  display: grid;\n}\n\n@media (max-width: 900px) and (min-width: 701px) {\n  .assistant-window {\n    right: 16px;\n    bottom: 16px;\n    width: calc(100vw - 32px);\n    height: min(820px, calc(100dvh - 32px));\n    border-radius: 24px;\n  }\n}\n\n@media (max-width: 700px) {\n  .assistant-button {\n    right: 12px;\n    bottom: calc(78px + env(safe-area-inset-bottom));\n    width: 56px;\n    min-width: 56px;\n    height: 56px;\n    padding: 7px;\n    border-radius: 18px;\n    gap: 0;\n  }\n\n  .assistant-button-mark {\n    width: 40px;\n    height: 40px;\n    flex-basis: 40px;\n  }\n\n  .assistant-button-copy,\n  .assistant-button-status {\n    display: none;\n  }\n\n  .assistant-window {\n    inset: 0;\n    width: 100%;\n    height: 100dvh;\n    min-height: 0;\n    border: 0;\n    border-radius: 0;\n    box-shadow: none;\n  }\n\n  .assistant-header {\n    min-height: 64px;\n    padding: calc(8px + env(safe-area-inset-top)) 10px 8px;\n  }\n\n  .assistant-avatar {\n    width: 39px;\n    height: 39px;\n    flex-basis: 39px;\n    border-radius: 12px;\n  }\n\n  .assistant-avatar img {\n    width: 31px;\n    height: 31px;\n  }\n\n  .assistant-kicker {\n    font-size: .55rem;\n  }\n\n  .assistant-header-info h3 {\n    font-size: .91rem;\n  }\n\n  .assistant-status {\n    margin-top: 3px;\n    font-size: .62rem;\n  }\n\n  .clear-cache,\n  .assistant-close {\n    width: 34px;\n    height: 34px;\n    border-radius: 10px;\n  }\n\n  .assistant-messages {\n    padding: 12px 9px 10px;\n    gap: 9px;\n  }\n\n  .message {\n    max-width: 94%;\n  }\n\n  .message.user {\n    max-width: 84%;\n  }\n\n  .message.assistant {\n    max-width: 96%;\n  }\n\n  .message.user .message-content {\n    padding: 9px 11px 7px;\n    font-size: .84rem;\n  }\n\n  .message.assistant .message-content {\n    padding: 11px 12px 8px;\n    font-size: .84rem;\n    line-height: 1.57;\n  }\n\n  .message.assistant p {\n    margin-bottom: 7px;\n    font-size: .84rem;\n  }\n\n  .message.assistant li {\n    margin: 3px 0;\n    font-size: .82rem;\n  }\n\n  .message.assistant h1 { font-size: 1.05rem; }\n  .message.assistant h2 { font-size: .98rem; }\n  .message.assistant h3 { font-size: .91rem; }\n\n  .message-time {\n    padding-bottom: 7px;\n    font-size: .58rem;\n  }\n\n  .feedback-buttons {\n    padding: 0 10px 9px;\n  }\n\n  .feedback-btn {\n    min-height: 26px;\n    padding: 4px 8px;\n    font-size: .65rem;\n  }\n\n  .quick-actions {\n    padding: 7px 8px 6px;\n    flex-wrap: nowrap;\n    overflow-x: auto;\n    gap: 6px;\n    scrollbar-width: none;\n  }\n\n  .quick-actions::-webkit-scrollbar {\n    display: none;\n  }\n\n  .quick-actions .btn {\n    min-height: 30px;\n    flex: 0 0 auto;\n    padding: 5px 9px;\n    font-size: .67rem;\n    white-space: nowrap;\n  }\n\n  .assistant-input-area {\n    padding: 7px 8px calc(8px + env(safe-area-inset-bottom));\n    gap: 6px;\n  }\n\n  .assistant-input-area input {\n    height: 42px;\n    padding: 0 12px;\n    border-radius: 13px;\n    font-size: .82rem;\n  }\n\n  .assistant-input-area button {\n    width: 44px;\n    min-width: 44px;\n    height: 42px;\n    padding: 0;\n    border-radius: 13px;\n    font-size: 0;\n  }\n\n  .assistant-input-area button::after {\n    content: \"➜\";\n    font-size: 1.02rem;\n    line-height: 1;\n  }\n\n  .back-to-bottom {\n    right: 10px;\n    bottom: calc(103px + env(safe-area-inset-bottom));\n    width: 34px;\n    height: 34px;\n    border-radius: 11px;\n  }\n}\n\n@media (max-width: 345px) {\n  .assistant-header {\n    padding-left: 8px;\n    padding-right: 8px;\n  }\n\n  .assistant-header-left {\n    gap: 8px;\n  }\n\n  .assistant-avatar {\n    width: 36px;\n    height: 36px;\n    flex-basis: 36px;\n  }\n\n  .assistant-header-info h3 {\n    font-size: .84rem;\n  }\n\n  .assistant-status {\n    font-size: .58rem;\n  }\n\n  .clear-cache,\n  .assistant-close {\n    width: 32px;\n    height: 32px;\n  }\n\n  .assistant-messages {\n    padding-left: 7px;\n    padding-right: 7px;\n  }\n\n  .message.assistant .message-content,\n  .message.user .message-content {\n    font-size: .8rem;\n  }\n\n  .quick-actions .btn {\n    font-size: .63rem;\n  }\n\n  .assistant-input-area input {\n    font-size: .78rem;\n  }\n}\n\n@media (prefers-reduced-motion: reduce) {\n  .assistant-button,\n  .assistant-window.open,\n  .message,\n  .typing-indicator span {\n    animation: none !important;\n    transition: none !important;\n  }\n}\n";
  document.head.appendChild(style);

  // ============================================================
  // INTERFACE UTILISATEUR
  // ============================================================

  const button = document.createElement('button');
  button.className = 'assistant-button';
  button.type = 'button';
  button.setAttribute('aria-label', 'Ouvrir l’assistant Mr XPRONOS');
  button.innerHTML = '<span class="assistant-button-mark"><img src="assets/images/mrxpronos-mark.webp" alt="" aria-hidden="true"></span><span class="assistant-button-copy"><strong>Assistant</strong><small>Mr XPRONOS</small></span><span class="assistant-button-status" aria-hidden="true"></span>';
  button.title = "Assistant Mr XPRONOS";
  document.body.appendChild(button);

  const windowDiv = document.createElement('div');
  windowDiv.className = 'assistant-window';
  windowDiv.setAttribute('role', 'dialog');
  windowDiv.setAttribute('aria-modal', 'true');
  windowDiv.setAttribute('aria-label', 'Assistant Mr XPRONOS');
  windowDiv.innerHTML = "\n    <div class=\"assistant-header\">\n      <div class=\"assistant-header-left\">\n        <div class=\"assistant-avatar\"><img src=\"assets/images/mrxpronos-mark.webp\" alt=\"\" aria-hidden=\"true\"></div>\n        <div class=\"assistant-header-info\">\n          <span class=\"assistant-kicker\">ASSISTANT IA</span>\n          <h3>Mr XPRONOS</h3>\n          <div class=\"assistant-status\">\n            <span class=\"status-dot\" aria-hidden=\"true\"></span>\n            <span>En ligne · réponses instantanées</span>\n          </div>\n        </div>\n      </div>\n      <div class=\"assistant-header-actions\">\n        <button class=\"clear-cache\" type=\"button\" title=\"Vider le cache des réponses\" aria-label=\"Vider le cache des réponses\">↻</button>\n        <button class=\"assistant-close\" type=\"button\" aria-label=\"Fermer l’assistant\">&times;</button>\n      </div>\n    </div>\n    <div class=\"assistant-messages\" id=\"assistant-messages\"></div>\n    <button class=\"back-to-bottom\" id=\"back-to-bottom\" type=\"button\" aria-label=\"Aller au dernier message\"><span aria-hidden=\"true\">↓</span></button>\n    <div class=\"assistant-suggestions\" id=\"assistant-suggestions\" style=\"display:none;\"></div>\n    <div class=\"quick-actions\" id=\"quick-actions\" aria-label=\"Raccourcis de l’assistant\"></div>\n    <div class=\"assistant-input-area\">\n      <input type=\"text\" id=\"assistant-input\" placeholder=\"Pose ta question…\" autocomplete=\"off\" aria-label=\"Question pour l’assistant\">\n      <button id=\"assistant-send\" type=\"button\" aria-label=\"Envoyer la question\">Envoyer</button>\n    </div>\n";
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

  function sanitizeAssistantHtml(inputHtml) {
    const allowed=new Set(['P','H3','H4','UL','OL','LI','A','TABLE','THEAD','TBODY','TR','TH','TD','STRONG','EM','BR','DIV','SPAN']);
    const doc=new DOMParser().parseFromString(String(inputHtml || ''),'text/html');
    const clean=(node)=>{
      if(node.nodeType===Node.TEXT_NODE)return document.createTextNode(node.textContent||'');
      if(node.nodeType!==Node.ELEMENT_NODE)return document.createDocumentFragment();
      const tag=node.tagName;
      if(['SCRIPT','STYLE','SVG','IFRAME','OBJECT','FORM','INPUT','BUTTON','IMG','META','LINK','TEMPLATE'].includes(tag))return document.createDocumentFragment();
      const fragment=document.createDocumentFragment();
      const safe=allowed.has(tag)?document.createElement(tag.toLowerCase()):fragment;
      if(tag==='A'&&safe!==fragment){
        try{
          const url=new URL(node.getAttribute('href')||'',location.origin);
          if(url.protocol==='https:'||url.protocol==='http:'){
            safe.setAttribute('href',url.href);safe.setAttribute('target','_blank');safe.setAttribute('rel','noopener noreferrer');
          }
        }catch(_){}
      }
      if(tag==='DIV'&&node.classList.contains('table-container'))safe.className='table-container';
      for(const child of Array.from(node.childNodes))safe.appendChild(clean(child));
      return safe;
    };
    const out=document.createElement('div');
    for(const node of Array.from(doc.body.childNodes))out.appendChild(clean(node));
    return out.innerHTML;
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
          '<p>👋 <strong>Bonjour !</strong> Je suis l’assistant Mr XPRONOS.</p><p>Pronostics, <strong>PRONO LIVE</strong>, bonus, historique ou aide : choisis un raccourci ou pose directement ta question.</p>',
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
      contentDiv.innerHTML = sanitizeAssistantHtml(cleaned);
    } else {
      contentDiv.textContent = text;
    }

    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = getCurrentTime();

    msgDiv.appendChild(contentDiv);
    msgDiv.appendChild(timeDiv);

    if (sender === 'assistant' && save) {
      const feedbackDiv = document.createElement('div');
      feedbackDiv.className = 'feedback-buttons';
      feedbackDiv.innerHTML = `
        <button class="feedback-btn like" data-id="${Number.isSafeInteger(Number(conversationId)) && conversationId ? Number(conversationId) : ''}">👍 Utile</button>
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
                question: msgDiv.previousElementSibling?.classList.contains('user') ? msgDiv.previousElementSibling.querySelector('.message-content')?.textContent : '',
                reponse: contentDiv.innerHTML,
                feedback: isLike
              })
            });

            if (response.ok) {
              feedbackDiv.querySelectorAll('.feedback-btn').forEach(b => { b.disabled = true; });
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
    quickActionsDiv.innerHTML='';
    const path=location.pathname.toLowerCase();
    const actions=path.includes('live.html')?[
      {label:'🔴 LIVE',value:'Comment fonctionne le PRONO LIVE ?'},
      {label:'📊 Signaux',value:'Que signifie un signal live ?'},
      {label:'🛟 Support',value:'Comment contacter le support ?'}
    ]:path.includes('historique.html')?[
      {label:'📈 Historique',value:'Comment interpréter le taux de réussite des pronostics ?'},
      {label:'🎯 Risques',value:'Pourquoi un pronostic peut échouer ?'}
    ]:path.includes('pronos.html')?[
      {label:'⚽ Pronostics',value:'Quels sont les pronostics du jour ?'},
      {label:'📊 Score xPronos',value:'Comment lire le score xPronos ?'},
      {label:'📋 Marchés',value:'Comment comprendre les différents marchés ?'}
    ]:[
      {label:'📊 Pronostics du jour',value:'Quels sont les pronostics du jour ?'},
      {label:'🎁 Code promo',value:'Comment utiliser le code XPVIP ?'},
      {label:'🔴 PRONO LIVE',value:'Comment accéder au PRONO LIVE ?'},
      {label:'📞 Support',value:'Comment contacter le support ?'}
    ];
    for(const a of actions){
      const btn=document.createElement('button');btn.className='btn';btn.textContent=a.label;
      btn.addEventListener('click',()=>{input.value=a.value;sendMessage();});quickActionsDiv.appendChild(btn);
    }
  }

  function buildHistoryPayload() {
    const history=[];
    let seenUser=false;
    for(const el of Array.from(messagesDiv.querySelectorAll('.message'))){
      const role=el.classList.contains('user')?'user':'assistant';
      if(role==='user')seenUser=true;
      if(!seenUser)continue;
      const content=el.querySelector('.message-content');
      if(content && content.textContent?.trim())history.push({role,contenu:content.textContent.trim().slice(0,1500)});
    }
    return history.slice(-8);
  }

  // ============================================================
  // ENVOI MESSAGE
  // ============================================================
  async function sendMessage() {
    const question = input.value.trim();
    if (!question || requestInFlight) return;
    const historique = buildHistoryPayload();
    requestInFlight = true;
    addMessage(question, 'user', false, null, true);
    input.value = '';
    showTyping();
    const cachedAnswer = getFromCache(question);
    const useCache = historique.length === 0 && !DYNAMIC_QUESTION.test(question) && cachedAnswer && !isNoPronoMessage(cachedAnswer);

    if (useCache) {
      hideTyping();
      addMessage(cachedAnswer, 'assistant', true, null, true);
      requestInFlight = false;
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
          historique: historique,
          page_context: { pathname: location.pathname }
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Erreur ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      hideTyping();

      const cleanedAnswer = cleanAssistantHtmlResponse(data.answer);

      if (historique.length === 0 && !DYNAMIC_QUESTION.test(question) && !isNoPronoMessage(cleanedAnswer)) {
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
    } finally {
      requestInFlight = false;
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