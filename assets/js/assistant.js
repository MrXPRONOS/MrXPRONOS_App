// assistant.js - Mr XPRONOS Assistant IA (Version Premium)
// Plein écran, couleurs conformes, liens bleus, espacement, F CFA, cache, personnalité professionnelle.
// Modifications : suggestions supprimées, bouton de vidage du cache ajouté, nettoyage automatique des entrées expirées.

(function() {
    "use strict";

    // ============================================================
    // CONFIGURATION
    // ============================================================
    const API_BASE = 'https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/assistant';
    
    // Suggestions désactivées (plus utilisées)
    const DEFAULT_SUGGESTIONS = [];

    // Cache local des réponses (24h)
    const CACHE_TTL = 24 * 60 * 60 * 1000;
    let responseCache = new Map();

    // Charger le cache depuis localStorage
    try {
        const cached = localStorage.getItem('assistant_response_cache');
        if (cached) {
            const parsed = JSON.parse(cached);
            responseCache = new Map(parsed);
        }
    } catch (e) {
        console.warn('Erreur chargement cache', e);
    }

    // Nettoyer les entrées expirées
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

    // Variables d'état
    let isOpen = false;
    let userId = localStorage.getItem('assistant_user_id') || 'user_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('assistant_user_id', userId);

    // Historique des questions (max 5)
    let questionHistory = JSON.parse(localStorage.getItem('assistant_history') || '[]').slice(-5);

    // Clé pour stocker les messages
    const MESSAGES_STORAGE_KEY = 'assistant_messages';

    // ============================================================
    // STYLES (avec ajout du bouton de vidage du cache)
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
            --blue-link: #3b82f6;
            --shadow-gold: 0 4px 20px rgba(212, 175, 55, 0.3);
            --border-gold: 1px solid rgba(212, 175, 55, 0.3);
        }

        * {
            box-sizing: border-box;
        }

        /* Bouton flottant */
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

        /* Fenêtre principale - PLEIN ÉCRAN */
        .assistant-window {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-card);
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

        /* Header */
        .assistant-header {
            background: linear-gradient(135deg, var(--bg-dark) 0%, var(--bg-card) 100%);
            padding: 16px 20px;
            border-bottom: 1px solid var(--gold);
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
            font-weight: 600;
        }
        
        .assistant-status {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.8rem;
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

        /* Bouton de vidage du cache */
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

        /* Zone des messages */
        .assistant-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-dark) 100%);
            scroll-behavior: smooth;
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

        /* Messages */
        .message {
            max-width: 90%;
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
        }

        .message.assistant {
            align-self: flex-start;
            background: var(--bg-elevated);
            color: var(--text-primary);
            border-bottom-left-radius: 4px;
            border: var(--border-gold);
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            max-width: 100%;
        }

        .message.assistant .message-content {
            padding: 16px;
            overflow-x: auto;
        }

        /* Formatage HTML */
        .message.assistant h1, .message.assistant h2, .message.assistant h3 {
            margin: 0 0 12px 0;
            color: var(--gold-light);
            font-weight: 600;
            line-height: 1.3;
        }
        
        .message.assistant h1 { font-size: 1.4rem; border-bottom: 2px solid var(--gold); padding-bottom: 8px; }
        .message.assistant h2 { font-size: 1.2rem; }
        .message.assistant h3 { font-size: 1.1rem; color: var(--gold); }
        
        .message.assistant p {
            margin: 0 0 12px 0;
        }
        .message.assistant p:last-child {
            margin-bottom: 0;
        }
        
        .message.assistant ul, .message.assistant ol {
            margin: 8px 0;
            padding-left: 20px;
        }
        
        .message.assistant li {
            margin: 4px 0;
        }
        
        .message.assistant ul li::marker {
            color: var(--gold);
        }
        
        .message.assistant blockquote {
            margin: 12px 0;
            padding: 12px 16px;
            background: rgba(212, 175, 55, 0.1);
            border-left: 4px solid var(--gold);
            border-radius: 0 8px 8px 0;
            font-style: italic;
            color: var(--text-secondary);
        }
        
        .message.assistant code {
            background: rgba(212, 175, 55, 0.15);
            color: var(--gold-light);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.9em;
        }
        
        .message.assistant pre {
            background: var(--bg-dark);
            border: 1px solid rgba(212, 175, 55, 0.2);
            border-radius: 8px;
            padding: 12px;
            overflow-x: auto;
            margin: 12px 0;
        }
        
        .message.assistant strong {
            color: var(--gold-light);
            font-weight: 600;
        }
        
        .message.assistant em {
            color: var(--gold);
            font-style: italic;
        }

        /* Liens en bleu clair */
        .message.assistant a {
            color: var(--blue-link);
            text-decoration: underline;
            transition: color 0.2s;
        }
        
        .message.assistant a:hover {
            color: #60a5fa;
        }

        /* Tableaux avec police réduite */
        .message.assistant .table-container {
            overflow-x: auto;
            margin: 12px 0;
            border-radius: 8px;
            border: var(--border-gold);
        }
        
        .message.assistant table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.75rem;
            background: var(--bg-dark);
        }
        
        .message.assistant th {
            background: linear-gradient(135deg, rgba(212, 175, 55, 0.2), rgba(212, 175, 55, 0.1));
            color: var(--gold-light);
            font-weight: 600;
            padding: 6px 8px;
            text-align: left;
            border-bottom: 2px solid var(--gold);
            white-space: nowrap;
        }
        
        .message.assistant td {
            padding: 6px 8px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            color: var(--text-primary);
        }
        
        .message.assistant tr:hover td {
            background: rgba(212, 175, 55, 0.05);
        }

        /* Horodatage - gris clair pour meilleure lisibilité */
        .message-time {
            font-size: 0.65rem;
            color: #9ca3af !important;
            margin-top: 4px;
            text-align: right;
            opacity: 0.9;
            padding: 0 16px 8px 16px;
        }
        
        .message.assistant .message-time {
            text-align: left;
            padding-left: 16px;
        }

        /* Boutons de feedback */
        .feedback-buttons {
            display: flex;
            gap: 8px;
            padding: 0 16px 16px 16px;
        }
        
        .feedback-btn {
            background: rgba(212, 175, 55, 0.1);
            border: 1px solid rgba(212, 175, 55, 0.3);
            border-radius: 20px;
            color: var(--gold);
            padding: 4px 12px;
            font-size: 0.8rem;
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

        /* Suggestions (désactivées) */
        .assistant-suggestions {
            padding: 12px;
            border-top: var(--border-gold);
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            background: var(--bg-dark);
            max-height: 80px;
            overflow-y: auto;
            display: none; /* caché */
        }
        
        .suggestion-chip {
            background: rgba(212, 175, 55, 0.1);
            border: 1px solid rgba(212, 175, 55, 0.25);
            border-radius: 30px;
            padding: 6px 12px;
            font-size: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 4px;
            font-weight: 500;
        }
        
        .suggestion-chip:hover {
            background: var(--gold);
            color: #000;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(212, 175, 55, 0.3);
        }

        /* Historique des questions */
        .assistant-history {
            padding: 0 12px 8px;
            border-top: var(--border-gold);
            background: var(--bg-dark);
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        .history-title {
            width: 100%;
            font-size: 0.8rem;
            color: #aaa;
            margin-bottom: 5px;
        }

        /* Actions rapides */
        .quick-actions {
            padding: 0 12px 12px;
            border-top: var(--border-gold);
            background: var(--bg-dark);
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }
        .quick-actions .btn {
            padding: 6px 12px;
            font-size: 0.75rem;
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

        /* Zone de saisie */
        .assistant-input-area {
            padding: 12px 16px;
            border-top: var(--border-gold);
            display: flex;
            gap: 8px;
            background: var(--bg-card);
            flex-wrap: wrap;
        }
        
        .assistant-input-area input {
            flex: 1;
            min-width: 200px;
            padding: 12px 16px;
            border-radius: 24px;
            border: var(--border-gold);
            background: var(--bg-dark);
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
            padding: 12px 20px;
            border-radius: 24px;
            border: none;
            background: linear-gradient(135deg, var(--gold), var(--gold-dark));
            color: #000;
            font-weight: 600;
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

        /* Indicateur de frappe */
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

        /* Responsive */
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
            .message {
                max-width: 95%;
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
        <div class="assistant-suggestions" id="assistant-suggestions" style="display: none;"></div>
        <div class="assistant-history" id="assistant-history"></div>
        <div class="quick-actions" id="quick-actions"></div>
        <div class="assistant-input-area">
            <input type="text" id="assistant-input" placeholder="Posez votre question...">
            <button id="assistant-send">Envoyer</button>
        </div>
    `;
    document.body.appendChild(windowDiv);

    // Références DOM
    const messagesDiv = document.getElementById('assistant-messages');
    const input = document.getElementById('assistant-input');
    const sendBtn = document.getElementById('assistant-send');
    const closeBtn = document.querySelector('.assistant-close');
    const clearCacheBtn = document.querySelector('.clear-cache');
    const suggestionsDiv = document.getElementById('assistant-suggestions');
    const historyDiv = document.getElementById('assistant-history');
    const quickActionsDiv = document.getElementById('quick-actions');

    // ============================================================
    // GESTION DE LA PERSISTANCE DES MESSAGES
    // ============================================================

    // Charger les messages sauvegardés
    function loadMessages() {
        try {
            const saved = localStorage.getItem(MESSAGES_STORAGE_KEY);
            if (saved) {
                const messages = JSON.parse(saved);
                messages.forEach(msg => {
                    addMessage(msg.text, msg.sender, msg.isHTML, msg.conversationId, false);
                });
            } else {
                // Message d'accueil par défaut
                addMessage(
                    `<p>👋 <strong>Bonjour !</strong> Je suis votre assistant personnel pour les paris sportifs.</p>
                     <p>Je peux vous aider avec :</p>
                     <ul>
                         <li>Les pronostics du jour ⚽</li>
                         <li>Les bonus bookmakers 🎁</li>
                         <li>Le <strong>LIVE VIP</strong> 🎥 (matchs en direct)</li>
                         <li>Vos questions sur le site 💡</li>
                     </ul>
                     <p>Tous les montants sont indiqués en <strong>Francs CFA</strong> (1€ ≈ 650 F CFA).</p>`,
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

    // Sauvegarder les messages (limiter à 20 derniers)
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

    // Modifier addMessage pour accepter un paramètre "save" optionnel
    function addMessage(text, sender, isHTML = false, conversationId = null, save = true) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}`;
        if (conversationId) {
            msgDiv.dataset.conversationId = conversationId;
        }
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (isHTML || sender === 'assistant') {
            contentDiv.innerHTML = text;
        } else {
            contentDiv.textContent = text;
        }
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = getCurrentTime();
        
        msgDiv.appendChild(contentDiv);
        msgDiv.appendChild(timeDiv);
        
        // Boutons de feedback pour les réponses de l'assistant
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
    // FONCTIONS UTILITAIRES
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

    // Détecte si la réponse est un message d'absence de pronostics
    function isNoPronoMessage(answer) {
        return answer.includes('Aucun pronostic disponible');
    }

    function formatMarkdown(text) {
        // Gardé pour compatibilité mais non utilisé si backend renvoie HTML
        if (!text) return '';
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        // Titres
        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2>$2</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
        // Gras et italique
        html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        // Code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Blocs de code
        html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        // Citations
        html = html.replace(/^&gt; (.*$)/gim, '<blockquote>$1</blockquote>');
        // Listes
        html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
        html = html.replace(/<\/ul>\s*<ul>/g, '');
        // Lignes horizontales
        html = html.replace(/^---$/gim, '<hr style="border: none; border-top: 1px solid rgba(212,175,55,0.3); margin: 16px 0;">');
        // Sauts de ligne
        html = html.replace(/\n/g, '<br>');
        // Tableaux simplifiés
        if (html.includes('|')) {
            const tableRegex = /((?:\|[^|\n]+\|+\n?)+)/g;
            html = html.replace(tableRegex, (match) => {
                const rows = match.trim().split('\n').filter(r => r.trim());
                if (rows.length < 2) return match;
                let tableHtml = '<div class="table-container"><table>';
                rows.forEach((row, i) => {
                    const cells = row.split('|').filter(c => c.trim());
                    const tag = i === 0 ? 'th' : 'td';
                    tableHtml += '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
                });
                tableHtml += '</table></div>';
                return tableHtml;
            });
        }
        return html;
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

    // Récupération des suggestions depuis l'API (désactivée)
    async function fetchSuggestions() {
        return []; // Plus de suggestions
    }

    // Rendu des suggestions (désactivé)
    async function renderSuggestions() {
        suggestionsDiv.innerHTML = '';
        // Ne rien afficher
    }

    // Rendu de l'historique des questions
    function renderHistory() {
        historyDiv.innerHTML = '';
        if (questionHistory.length === 0) return;
        const title = document.createElement('div');
        title.className = 'history-title';
        title.textContent = 'Questions récentes :';
        historyDiv.appendChild(title);
        questionHistory.slice().reverse().forEach(q => {
            const chip = document.createElement('span');
            chip.className = 'suggestion-chip';
            chip.textContent = q;
            chip.addEventListener('click', () => {
                input.value = q;
                sendMessage();
            });
            historyDiv.appendChild(chip);
        });
    }

    // Rendu des actions rapides
    function renderQuickActions() {
        quickActionsDiv.innerHTML = '';
        const actions = [
            { label: '📊 Pronostics du jour', value: 'Quels sont les pronostics du jour ?' },
            { label: '🎁 Bonus 1xBet', value: 'Quel est le bonus 1xBet avec XPVIP ?' },
            { label: '🎥 LIVE VIP', value: 'Comment accéder au LIVE VIP ?' },
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

    // Construire l'historique des messages pour l'envoyer au backend
    function buildHistoryPayload() {
        const messages = [];
        const msgElements = messagesDiv.querySelectorAll('.message');
        // Prendre les 10 derniers messages maximum
        const recent = Array.from(msgElements).slice(-10);
        recent.forEach(el => {
            const role = el.classList.contains('user') ? 'user' : 'assistant';
            const contentEl = el.querySelector('.message-content');
            const contenu = role === 'assistant' ? contentEl.innerHTML : contentEl.textContent;
            messages.push({ role, contenu });
        });
        return messages;
    }

    // Envoi du message avec cache et historique
    async function sendMessage() {
        const question = input.value.trim();
        if (!question) return;
        
        addMessage(question, 'user', false, null, true);
        input.value = '';
        showTyping();

        if (!questionHistory.includes(question)) {
            questionHistory.push(question);
            if (questionHistory.length > 5) questionHistory.shift();
            localStorage.setItem('assistant_history', JSON.stringify(questionHistory));
            renderHistory();
        }

        // Vérifier le cache local (seulement si pas d'historique)
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
            
            // Mettre en cache seulement si pas d'historique et pas un message d'absence
            if (historique.length === 0 && !isNoPronoMessage(data.answer)) {
                addToCache(question, data.answer);
            }
            
            addMessage(data.answer, 'assistant', true, data.conversation_id, true);
            
        } catch (error) {
            hideTyping();
            addMessage(
                "❌ **Oups !** Une erreur est survenue. Veuillez réessayer plus tard.\n\n" +
                `_Erreur technique : ${error.message}_`, 
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
            button.classList.add('hidden');
            input.focus();
            renderSuggestions(); // ne fait rien
            renderHistory();
            renderQuickActions();
        } else {
            button.classList.remove('hidden');
        }
    });

    closeBtn.addEventListener('click', () => {
        isOpen = false;
        windowDiv.classList.remove('open');
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
            button.classList.remove('hidden');
        }
    });

    // Restaurer les messages au chargement
    loadMessages();

    console.log('🎯 Mr XPRONOS Assistant chargé avec succès (version améliorée avec persistance et historique)');
})();