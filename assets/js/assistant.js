// assistant.js - Mr XPRONOS Assistant IA (Version Premium)

(function() {
    "use strict";

    const API_BASE = 'https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/assistant';
    
    const SUGGESTIONS = [
        { icon: '🎯', text: "Pronostic du jour" },
        { icon: '🎁', text: "Bonus 1xBet XPVIP" },
        { icon: '💰', text: "Meilleures cotes" },
        { icon: '🚀', text: "Inscription 1win" },
        { icon: '💡', text: "Conseils paris" }
    ];

    let isOpen = false;
    let userId = localStorage.getItem('assistant_user_id') || 'user_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('assistant_user_id', userId);

    // ==========================================
    // STYLES - Version finale (couleurs du site)
    // ==========================================
    const style = document.createElement('style');
    style.textContent = `
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
        
        :root {
            --gold-primary: #D4AF37;      /* Or du site */
            --gold-light: #FFD700;
            --gold-dark: #B8941F;
            --bg-dark: #0D0D0D;
            --bg-card: #1A1A1A;
            --bg-elevated: #252525;
            --text-primary: #FFFFFF;
            --text-secondary: #A0A0A0;
            --accent-green: #22C55E;
            --accent-red: #EF4444;
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
            background: linear-gradient(135deg, var(--gold-primary) 0%, var(--gold-light) 50%, var(--gold-primary) 100%);
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
            background: linear-gradient(135deg, var(--gold-light) 0%, var(--gold-primary) 100%);
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

        .assistant-header {
            background: linear-gradient(135deg, var(--bg-dark) 0%, var(--bg-card) 100%);
            padding: 16px 20px;
            border-bottom: 1px solid var(--gold-primary);
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
            background: linear-gradient(135deg, var(--gold-primary), var(--gold-light));
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
            color: var(--gold-primary);
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
            background: var(--gold-primary);
            border-radius: 3px;
        }

        .message {
            max-width: 90%;
            padding: 0;
            border-radius: 16px;
            word-wrap: break-word;
            font-size: 0.95rem;
            line-height: 1.6;
            animation: message-appear 0.3s ease-out;
        }
        
        @keyframes message-appear {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            align-self: flex-end;
            background: linear-gradient(135deg, var(--gold-primary) 0%, var(--gold-dark) 100%);
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

        /* Style des paragraphes avec espacement */
        .message.assistant p {
            margin: 0 0 12px 0;
        }
        .message.assistant p:last-child {
            margin-bottom: 0;
        }

        /* Liens en bleu clair */
        .message.assistant a {
            color: #64B5F6;  /* Bleu clair */
            text-decoration: underline;
            transition: color 0.2s;
        }
        
        .message.assistant a:hover {
            color: #90CAF9;
        }

        /* Heure en gris lisible */
        .message-time {
            font-size: 0.7rem;
            color: #B0B0B0;  /* Gris clair */
            margin-top: 4px;
            text-align: right;
            padding: 0 16px 8px 16px;
        }
        
        .message.assistant .message-time {
            text-align: left;
            padding-left: 16px;
        }

        /* Tableaux responsives */
        .message.assistant table {
            font-size: 0.8rem;
            border-collapse: collapse;
            width: 100%;
        }
        .message.assistant th, .message.assistant td {
            border: 1px solid #444;
            padding: 6px;
        }
        .message.assistant th {
            background: rgba(212, 175, 55, 0.2);
        }

        /* Feedback buttons */
        .feedback-buttons {
            display: flex;
            gap: 8px;
            padding: 0 16px 16px 16px;
        }
        
        .feedback-btn {
            background: rgba(212, 175, 55, 0.1);
            border: 1px solid rgba(212, 175, 55, 0.3);
            border-radius: 20px;
            color: var(--gold-primary);
            padding: 4px 12px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .feedback-btn:hover {
            background: var(--gold-primary);
            color: #000;
        }
        
        .feedback-btn:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }

        /* Suggestions */
        .assistant-suggestions {
            padding: 12px;
            border-top: var(--border-gold);
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            background: var(--bg-dark);
            max-height: 80px;
            overflow-y: auto;
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
        }
        
        .suggestion-chip:hover {
            background: var(--gold-primary);
            color: #000;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(212, 175, 55, 0.3);
        }

        .assistant-input-area {
            padding: 12px 16px;
            border-top: var(--border-gold);
            display: flex;
            gap: 8px;
            background: var(--bg-card);
        }
        
        .assistant-input-area input {
            flex: 1;
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
            border-color: var(--gold-primary);
            box-shadow: 0 0 0 2px rgba(212, 175, 55, 0.2);
        }
        
        .assistant-input-area button {
            padding: 12px 20px;
            border-radius: 24px;
            border: none;
            background: linear-gradient(135deg, var(--gold-primary), var(--gold-dark));
            color: #000;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 4px 12px rgba(212, 175, 55, 0.3);
        }
        
        .assistant-input-area button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(212, 175, 55, 0.4);
        }

        .typing-indicator {
            display: flex;
            gap: 4px;
            padding: 12px 16px;
            background: var(--bg-elevated);
            border-radius: 16px;
            align-self: flex-start;
            border: var(--border-gold);
            width: fit-content;
        }
        
        .typing-indicator span {
            width: 8px;
            height: 8px;
            background: var(--gold-primary);
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
            .assistant-header-info h3 { font-size: 1rem; }
            .assistant-avatar { width: 36px; height: 36px; font-size: 20px; }
            .assistant-close { font-size: 1.8rem; width: 40px; height: 40px; }
            .message { max-width: 95%; }
        }
    `;
    document.head.appendChild(style);

    // ==========================================
    // Interface
    // ==========================================
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
                        <span>Expert en ligne</span>
                    </div>
                </div>
            </div>
            <button class="assistant-close">&times;</button>
        </div>
        <div class="assistant-messages" id="assistant-messages">
            <div class="message assistant">
                <div class="message-content">
                    <p>👋 <strong>Bonjour !</strong> Je suis votre expert personnel pour les paris sportifs.</p>
                    <p>Je peux vous aider avec :</p>
                    <ul>
                        <li>Les pronostics du jour ⚽</li>
                        <li>Les bonus bookmakers 🎁</li>
                        <li>Vos questions sur le site 💡</li>
                    </ul>
                </div>
                <div class="message-time">${new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</div>
            </div>
        </div>
        <div class="assistant-suggestions" id="assistant-suggestions"></div>
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
    const suggestionsDiv = document.getElementById('assistant-suggestions');

    // Fonctions
    function getCurrentTime() {
        return new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    }

    function addMessage(text, sender, isHTML = false, conversationId = null) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = isHTML ? text : text.replace(/\n/g, '<br>');
        
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
            messagesDiv.scrollTo({ top: messagesDiv.scrollHeight, behavior: 'smooth' });
        }, 100);
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

    function renderSuggestions() {
        suggestionsDiv.innerHTML = '';
        SUGGESTIONS.forEach(s => {
            const chip = document.createElement('span');
            chip.className = 'suggestion-chip';
            chip.innerHTML = `${s.icon} ${s.text}`;
            chip.addEventListener('click', () => {
                input.value = s.text;
                sendMessage();
            });
            suggestionsDiv.appendChild(chip);
        });
    }

    async function sendMessage() {
        const question = input.value.trim();
        if (!question) return;
        
        addMessage(question, 'user');
        input.value = '';
        showTyping();

        try {
            const response = await fetch(API_BASE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question, user_id: userId })
            });
            
            if (!response.ok) {
                throw new Error(`Erreur ${response.status}`);
            }
            
            const data = await response.json();
            hideTyping();
            addMessage(data.answer, 'assistant', true, data.conversation_id);
            
        } catch (error) {
            hideTyping();
            addMessage("❌ Une erreur est survenue. Veuillez réessayer plus tard.", 'assistant');
            console.error(error);
        }
    }

    // Événements
    button.addEventListener('click', () => {
        isOpen = !isOpen;
        windowDiv.classList.toggle('open', isOpen);
        if (isOpen) {
            button.classList.add('hidden');
            input.focus();
            renderSuggestions();
        } else {
            button.classList.remove('hidden');
        }
    });

    closeBtn.addEventListener('click', () => {
        isOpen = false;
        windowDiv.classList.remove('open');
        button.classList.remove('hidden');
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

    console.log('✅ Assistant IA chargé (version finale)');
})();