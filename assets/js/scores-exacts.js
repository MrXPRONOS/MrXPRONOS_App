/* Mr XPRONOS — Daily Top5 exact scores; never invent or reuse stale forecasts. */
(() => {
  'use strict';
  const VERSION = 'mrx-exact-top5-v1';
  const MODEL = 'machine_learning_v3_hybrid';
  const GROUPS = Object.freeze({
    H_LOW: ['1:0', '2:0', '2:1'],
    H_HIGH: ['3:0', '3:1', '3:2'],
    A_LOW: ['0:1', '0:2', '1:2'],
    A_HIGH: ['0:3', '1:3', '2:3'],
    DRAW_LOW: ['0:0', '1:1', '2:2']
  });
  const status = document.getElementById('scores-status');
  const simpleRoot = document.getElementById('scores-simple-list');
  const groupedRoot = document.getElementById('scores-grouped-list');
  if (!status || !simpleRoot || !groupedRoot) return;

  const todayUTC = () => new Date().toISOString().slice(0, 10);
  const utcDay = (offset = 0) => new Date(Date.parse(todayUTC() + 'T00:00:00Z') + offset * 86400000).toISOString().slice(0, 10);
  const isScore = (s) => typeof s === 'string' && /^(?:10|[0-9]):(?:10|[0-9])$/.test(s);
  const text = (value) => String(value == null ? '' : value);
  const pct = (p) => (100 * p).toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + ' %';
  const make = (tag, cls, value) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (value !== undefined) node.textContent = text(value);
    return node;
  };
  const validDate = (s) => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s) &&
    Number.isFinite(Date.parse(s + 'T00:00:00Z')) && new Date(s + 'T00:00:00Z').toISOString().slice(0, 10) === s;
  const isoTime = (s) => typeof s === 'string' &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(s) &&
    Number.isFinite(Date.parse(s));
  const niceDate = (d) => new Date(d + 'T12:00:00Z').toLocaleDateString('fr-FR', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'
  });
  const clock = (iso) => new Date(iso).toLocaleTimeString('fr-FR', {
    hour: '2-digit', minute: '2-digit', timeZone: 'UTC'
  });
  const initial = (name) => text(name).trim().split(/\s+/).slice(0, 2).map(w => w[0] || '').join('').toUpperCase().slice(0, 3);

  function renderEmpty(root, message) {
    root.replaceChildren(make('p', 'mx-scores-empty', message));
  }

  function setStatus(message, state) {
    status.dataset.state = state;
    status.textContent = message;
  }

  function validPick(p, mode, day, produced) {
    if (!p || typeof p !== 'object' || Array.isArray(p) ||
        !p.id || typeof p.id !== 'string' || p.id.length > 150 ||
        typeof p.home !== 'string' || !p.home.trim() || p.home.length > 120 ||
        typeof p.away !== 'string' || !p.away.trim() || p.away.length > 120 ||
        typeof p.league !== 'string' || p.league.length > 140 ||
        !isScore(p.score) || !isoTime(p.kickoff_utc) ||
        p.kickoff_utc.slice(0, 10) !== day || Date.parse(p.kickoff_utc) <= produced ||
        !Number.isFinite(p.probability) || p.probability <= 0 || p.probability > 1) {
      return false;
    }
    if (mode === 'grouped') {
      return typeof p.group === 'string' &&
        Object.hasOwn(GROUPS, p.group) && GROUPS[p.group].includes(p.score) &&
        Array.isArray(p.group_scores) &&
        p.group_scores.length === 3 &&
        GROUPS[p.group].every((s, i) => p.group_scores[i] === s);
    }
    return p.group === undefined && p.group_scores === undefined;
  }

  function validate(payload, requestedDay) {
    if (!payload || payload.status === 'unavailable') return { available: false, message: 'Aucune sélection Hybride V3 vérifiée publiée pour le ' + niceDate(requestedDay) + '.' };
    if (payload.schema_version !== VERSION || payload.model !== MODEL || payload.status !== 'published')
      return { available: false, message: 'Format des prévisions non reconnu. Publication indisponible.' };
    const today = requestedDay;
    if (!validDate(payload.date) || payload.date !== today)
      return { available: false, message: 'La date du fichier ne correspond pas à la journée sélectionnée.' };
    const prior = new Date(Date.parse(today + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10);
    if (!isoTime(payload.generated_at) || ![today, prior].includes(payload.generated_at.slice(0, 10)) ||
        Date.parse(payload.generated_at) > Date.now() + 60000)
      return { available: false, message: 'La date de génération des pronostics n’est pas valide.' };
    if (!Array.isArray(payload.simple) || !Array.isArray(payload.grouped) ||
        payload.simple.length > 5 || payload.grouped.length > 5)
      return { available: false, message: 'Liste des sélections incomplète ou incorrecte.' };
    const generation = Date.parse(payload.generated_at);
    for (const mode of ['simple', 'grouped']) {
      const ids = new Set();
      for (const p of payload[mode]) {
        if (!validPick(p, mode, today, generation) || ids.has(p.id))
          return { available: false, message: 'Des informations de match ou de score sont invalides.' };
        ids.add(p.id);
      }
    }
    // Production 1:1 suppression also applies to previously archived daily
    // receipts. Keep their historical JSON intact, but never show the banned
    // exact score or any three-score group containing it on the live website.
    const filtered = {
      ...payload,
      simple: payload.simple.filter(p => p.score !== '1:1'),
      grouped: payload.grouped.filter(p => p.score !== '1:1' && !p.group_scores.includes('1:1'))
    };
    return { available: true, payload: filtered };
  }

  function team(name) {
    const block = make('div', 'mx-score-team');
    const badge = make('span', 'mx-score-initial', initial(name));
    badge.setAttribute('aria-hidden', 'true');
    block.append(badge, make('span', 'mx-score-teamname', name));
    return block;
  }

  function card(p, rank, mode) {
    const root = make('article', 'mx-score-card');
    const top = make('div', 'mx-score-card-top');
    top.append(
      make('span', 'mx-score-rank', '#' + rank),
      make('span', 'mx-score-league', p.league || 'Football'),
      make('time', 'mx-score-time', clock(p.kickoff_utc) + ' UTC')
    );
    top.lastChild.dateTime = p.kickoff_utc;
    const kickoffPassed = Date.parse(p.kickoff_utc) <= Date.now();
    if (kickoffPassed) {
      top.lastChild.classList.add('is-started');
      top.append(make('span', 'mx-score-foot-label is-archive', 'Coup d’envoi passé'));
    }
    const match = make('div', 'mx-score-match');
    const middle = make('div', 'mx-score-score');
    middle.append(
      make('strong', '', p.score.replace(':', ' : ')),
      make('small', '', mode === 'simple' ? 'Score exact' : 'Score modal')
    );
    match.append(team(p.home), middle, team(p.away));
    root.append(top, match);

    if (mode === 'grouped') {
      const chips = make('div', 'mx-score-chips');
      chips.setAttribute('aria-label', 'Scores couverts par le groupe');
      p.group_scores.forEach(score => {
        const chip = make('span', 'mx-score-chip' + (score === p.score ? ' is-modal' : ''), score.replace(':', ' - '));
        chips.append(chip);
      });
      root.append(chips);
    }
    const foot = make('div', 'mx-score-foot');
    foot.append(
      make('span', 'mx-score-foot-label',
        mode === 'simple' ? 'Probabilité du score' : 'Probabilité totale du groupe'),
      make('strong', 'mx-score-probability', pct(p.probability))
    );
    root.append(foot);
    return root;
  }

  function paint(root, picks, mode) {
    root.replaceChildren();
    if (!picks.length) {
      renderEmpty(root, mode === 'simple'
        ? 'Aucun score exact simple confirmé pour cette journée.'
        : 'Aucun groupe de trois scores admissible pour cette journée.');
      return;
    }
    picks.forEach((p, i) => root.append(card(p, i + 1, mode)));
  }


  let activePayload = null;
  let selectedOffset = 0;
  let requestSerial = 0;
  const dayButtons = Array.from(document.querySelectorAll('[data-scores-day]'));

  function renderDay(p) {
    // Past published predictions remain visible as dated archives,
    // never presented as currently bettable after kickoff.
    const started = [...p.simple, ...p.grouped].filter(item => Date.parse(item.kickoff_utc) <= Date.now()).length;
    paint(simpleRoot, p.simple, 'simple');
    paint(groupedRoot, p.grouped, 'grouped');
    document.getElementById('simple-count').textContent = p.simple.length + ' / 5';
    document.getElementById('grouped-count').textContent = p.grouped.length + ' / 5';
    document.getElementById('scores-updated').textContent =
      'Généré le ' + niceDate(p.generated_at.slice(0, 10)) + ' à ' + clock(p.generated_at) + ' UTC';
    const historical = selectedOffset < 0 || started > 0;
    const state = historical ? 'archive' : 'ready';
    const label = selectedOffset < 0 ? 'Archive de pronostics pré-match' :
      selectedOffset > 0 ? 'Prévisions prospectives pour demain' : 'Sélections pré-match du jour';
    setStatus(label + ' · ' + p.simple.length + ' score(s) simple(s), ' +
      p.grouped.length + ' groupe(s).' +
      (historical ? ' Les matchs dont le coup d’envoi est passé ne sont plus à parier.' : ''),
      state);
  }

  async function load() {
    const ownRequest = ++requestSerial;
    const requestedDay = utcDay(selectedOffset);
    document.getElementById('scores-date').textContent = 'Sélections du ' + niceDate(requestedDay);
    try {
      const res = await fetch('scores-exacts-daily/' + requestedDay + '.json?t=' + Date.now(), {
        cache: 'no-store', headers: { Accept: 'application/json' }
      });
      if (ownRequest !== requestSerial) return;
      if (!res.ok) throw new Error('Missing verified daily archive');
      const result = validate(await res.json(), requestedDay);
      if (ownRequest !== requestSerial) return;
      if (!result.available) {
        activePayload = null;
        setStatus(result.message, 'unavailable');
        renderEmpty(simpleRoot, 'Aucun Top 5 simple vérifié pour cette date.');
        renderEmpty(groupedRoot, 'Aucun Top 5 groupé vérifié pour cette date.');
        document.getElementById('simple-count').textContent = '0 / 5';
        document.getElementById('grouped-count').textContent = '0 / 5';
        return;
      }
      activePayload = result.payload;
      renderDay(activePayload);
    } catch (_) {
      if (ownRequest !== requestSerial) return;
      activePayload = null;
      setStatus('Pas de publication vérifiée pour le ' + niceDate(requestedDay) + '.', 'unavailable');
      renderEmpty(simpleRoot, 'Les scores exacts ne sont pas encore disponibles pour cette journée.');
      renderEmpty(groupedRoot, 'Les paris groupés ne sont pas encore disponibles pour cette journée.');
      document.getElementById('simple-count').textContent = '0 / 5';
      document.getElementById('grouped-count').textContent = '0 / 5';
    }
  }

  dayButtons.forEach(btn => btn.addEventListener('click', () => {
    selectedOffset = Number(btn.dataset.scoresDay);
    dayButtons.forEach(b => {
      const active = b === btn;
      b.classList.toggle('is-active', active);
      b.setAttribute('aria-pressed', String(active));
    });
    activePayload = null;
    setStatus('Vérification des pronostics de cette journée…', 'loading');
    load();
  }));

  // Keep the shared header promo button usable without loading the full
  // pronostics engine or fetching unrelated production data.
  const promo = document.querySelector('.mx-code-button');
  promo?.addEventListener('click', async () => {
    const value = promo.querySelector('strong')?.textContent?.trim() || 'XPVIP';
    if (!value || !navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(value);
      const original = promo.getAttribute('aria-label') || 'Code promo XPVIP';
      promo.setAttribute('aria-label', 'Code promo copié');
      window.setTimeout(() => promo.setAttribute('aria-label', original), 1600);
    } catch (_) {
      // The code remains visibly readable if clipboard access is blocked.
    }
  });

  const buttons = Array.from(document.querySelectorAll('[data-scores-mode]'));
  const panels = Array.from(document.querySelectorAll('[data-scores-panel]'));
  buttons.forEach(btn => btn.addEventListener('click', () => {
    const mode = btn.dataset.scoresMode;
    buttons.forEach(b => {
      const selected = b === btn;
      b.classList.toggle('is-active', selected);
      b.setAttribute('aria-pressed', String(selected));
    });
    panels.forEach(p => p.classList.toggle('is-active', p.dataset.scoresPanel === mode));
    if (window.matchMedia('(min-width:741px)').matches) {
      const panel = panels.find(p => p.dataset.scoresPanel === mode);
      panel?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }));

  // Refresh each selected calendar date when returning to the site.
  // At midnight, relative tabs roll forward, without treating old scores as new.
  let lastDay = todayUTC();
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
  window.setInterval(() => {
    if (document.hidden) return;
    if (todayUTC() !== lastDay) {
      lastDay = todayUTC();
      load();
    } else if (activePayload) {
      renderDay(activePayload);
    }
  }, 60000);
  window.setInterval(() => { if (!document.hidden) load(); }, 15 * 60000);
  load();
})();
