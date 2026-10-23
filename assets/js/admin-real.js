import { initAdminMfaControl } from "./admin-mfa-ui.mjs";
import { mountCmsBlockEditor } from "./cms-block-editor.mjs";
import { mountCmsRevisionPanel } from "./cms-revisions.mjs";
import { createCmsDraftCopy } from "./cms-duplicate.mjs";
import { mountCmsListFilters } from "./cms-list-filters.mjs";
import { mountCmsMediaFieldPicker, mountCmsMediaPicker } from "./cms-media-library.mjs";
import {neonAuthUrl,neonDataApiUrl} from "./config.js";
import {createClient, NeonAuthAdapter} from "https://esm.sh/@neondatabase/neon-js";
import "./loading-ui.js";


// Charger la feuille de style sans modifier la page de connexion administrateur.
if (!document.querySelector('link[href*="loading-ui.css"]')) {
  const mxLoadingSheet = document.createElement("link");
  mxLoadingSheet.rel = "stylesheet";
  mxLoadingSheet.href = "assets/css/loading-ui.css?v=20261012-3";
  document.head.appendChild(mxLoadingSheet);
}

const sb = createClient({auth:{adapter:NeonAuthAdapter(),url:neonAuthUrl},dataApi:{url:neonDataApiUrl}});
const adminApiUrl = String(window.MX_ADMIN_API_URL||"").replace(/\/$/,"");
const $ = (id) => document.getElementById(id);

const premiumAdminLoading = (kind = "admin", count = 3) =>
  window.MXLoading?.render?.(kind, count) || '<div class="muted">Chargement…</div>';


const TAB_NAMES = ["overview","pronostics","push","articles","conseils","bonus","infos","media","vip","health","audit"];
const loadedTabs = new Set();
let publishBusy = false;

function tabs() {
  return Array.from(document.querySelectorAll(".tab"));
}

function showOnlyTab(name) {
  tabs().forEach(t => {
    const active=t.dataset.tab===name;
    t.classList.toggle("active",active);
    t.setAttribute("aria-current",active?"page":"false");
  });
  TAB_NAMES.forEach(n => {
    const el = $(`tab-${n}`);
    if (!el) return;
    const active=n===name;
    el.hidden=!active;
    el.classList.toggle("active-screen",active);
  });
}

async function isAdmin() {
  const { data, error } = await sb.rpc("is_admin");
  if (error) return false;
  return data === true;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = String(s ?? "");
  return div.innerHTML;
}

function safeIdEq(a, b) {
  return String(a) === String(b);
}

// -----------------------------
// LAZY LOAD : charge la tab 1 fois
// -----------------------------
const TAB_LOADERS = {
  overview: async () => {},
  pronostics: renderPronosticsReadOnly,
  push: renderPushAdmin,
  articles: renderCmsArticles,
  conseils: renderCmsConseils,
  bonus: renderBonus,
  infos: renderInfos,
  media: renderMediaTab,
  vip: renderVip,
  health: renderHealth,
  audit: renderAudit,
};

async function loadTabIfNeeded(name) {
  if (loadedTabs.has(name)) return;
  const loader = TAB_LOADERS[name];
  if (typeof loader === "function") {
    await loader();
    loadedTabs.add(name);
  }
}

async function showTab(name) {
  if (!TAB_NAMES.includes(name)) name="overview";
  showOnlyTab(name);
  window.dispatchEvent(new CustomEvent("mx:admin-tab",{detail:{name}}));
  const target="#"+name;
  if (location.hash!==target) history.replaceState(null,"",target);
  await loadTabIfNeeded(name);
}
window.MXAdminNavigate = showTab;

// -----------------------------
// UI helpers
// -----------------------------
function setLoginMsg(msg) {
  const el = $("loginMsg");
  if (el) el.textContent = msg || "";
}

function setBtnDisabled(id, disabled) {
  const btn = $(id);
  if (btn) btn.disabled = !!disabled;
}


// -----------------------------
// PUSH (admin -> Edge Function admin-push -> push-notifications)
// + Ciblage: tous OU un user_id
// + Champs: title/body/url/tag
// + Bonus: bouton "Lister les abonnés" (Edge Function admin-list-subscribers)
// -----------------------------
async function renderPushAdmin() {
  const root = $("tab-push");
  if (!root) return;

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Envoyer une notification PUSH</h3>
      <div class="muted" style="margin-bottom:12px;">
        Notifications reçues uniquement par les utilisateurs <b>abonnés</b> (permission activée).
      </div>

      <div class="row">
        <div>
          <label>Audience</label>
          <select id="push_audience">
            <option value="all">Tous les abonnés</option>
            <option value="user">Un utilisateur (user_id)</option>
          </select>
        </div>

        <div id="push_user_wrap" style="display:none;">
          <label>User ID (ex: MX-xxxx...)</label>
          <input id="push_user_id" placeholder="MX-..." />
          <div class="muted" style="margin-top:6px;">
            Cliquez sur un abonné dans la liste (en bas) pour remplir automatiquement.
          </div>
        </div>
      </div>

      <label style="margin-top:10px;">Titre</label>
      <input id="push_title" placeholder="Ex: Nouveaux coupons !" />

      <label>Message</label>
      <textarea id="push_body" rows="4" placeholder="Ex: Les pronostics du jour sont disponibles."></textarea>

      <label>URL au clic (optionnel)</label>
      <input id="push_url" placeholder="https://..." value="https://mrxpronos.github.io/MrXPRONOS_App/pronos.html" />

      <div class="row">
        <div>
          <label>Tag (optionnel)</label>
          <input id="push_tag" placeholder="Ex: coupons-matin" />
        </div>
        <div>
          <label>&nbsp;</label>
          <button id="push_send" class="btn btn-primary" style="width:100%;">Envoyer</button>
        </div>
      </div>

      <div id="push_status" class="muted" style="margin-top:10px"></div>
      <div id="push_results" style="margin-top:10px"></div>
    </div>

    <div class="card" style="border-color:#2a2a2a;">
      <div style="display:flex; gap:10px; justify-content:space-between; align-items:center; flex-wrap:wrap;">
        <h3 style="margin:0;color:#D4AF37">Abonnés PUSH</h3>
        <div style="display:flex; gap:10px; flex-wrap:wrap;">
          <input id="subs_search" placeholder="Rechercher un user_id (MX-...)" style="max-width:320px;">
          <button id="subs_refresh" class="btn btn-secondary">Lister les abonnés</button>
        </div>
      </div>
      <div id="subs_status" class="muted" style="margin-top:10px"></div>
      <div id="subs_list" class="muted" style="margin-top:10px">Clique sur “Lister les abonnés”.</div>
    </div>
  `;

  const setStatus = (msg) => {
    const el = $("push_status");
    if (el) el.textContent = msg || "";
  };

  const renderResults = (data) => {
    const el = $("push_results");
    if (!el) return;

    const results = Array.isArray(data?.results) ? data.results : [];
    const sent = results.filter(r => r.status === "sent").length;
    const deleted = results.filter(r => r.status === "deleted_410").length;
    const failed = results.filter(r => r.status === "failed").length;
    const skipped = results.filter(r => String(r.status || "").startsWith("skipped")).length;

    el.innerHTML = `
      <div class="card" style="border-color:#2a2a2a;">
        <div style="font-weight:900;color:#D4AF37;margin-bottom:6px;">Résultat</div>
        <div class="muted">
          Envoyés: ${sent} • Supprimés (410): ${deleted} • Échecs: ${failed} • Ignorés: ${skipped} • Total: ${results.length}
        </div>
        <details style="margin-top:10px;">
          <summary class="muted" style="cursor:pointer;">Détails (JSON)</summary>
          <pre class="muted" style="margin-top:10px;">${escapeHtml(JSON.stringify(data, null, 2))}</pre>
        </details>
      </div>
    `;
  };

  async function callAdminPush(payload) {
    const session = (await sb.auth.getSession()).data.session;
    if (!session) throw new Error("Session expirée.");

    if (!adminApiUrl) throw new Error("API administrateur Cloudflare non configurée");
    const res = await fetch(`${adminApiUrl}/admin-push`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || `Erreur HTTP ${res.status}`);
    return data;
  }

  async function callListSubscribers() {
    const session = (await sb.auth.getSession()).data.session;
    if (!session) throw new Error("Session expirée.");

    if (!adminApiUrl) throw new Error("API administrateur Cloudflare non configurée");
    const res = await fetch(`${adminApiUrl}/admin-list-subscribers`, {
      method: "GET",
      headers: {
        "Authorization": `Bearer ${session.access_token}`,
      },
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || `Erreur HTTP ${res.status}`);
    return data;
  }

  // Audience toggle
  const audienceSel = $("push_audience");
  const userWrap = $("push_user_wrap");
  const userInput = $("push_user_id");

  function refreshAudience() {
    const mode = audienceSel.value;
    userWrap.style.display = mode === "user" ? "block" : "none";
  }
  audienceSel.addEventListener("change", refreshAudience);
  refreshAudience();

  // Envoi push
  $("push_send").addEventListener("click", async () => {
    const mode = audienceSel.value;
    const title = $("push_title").value.trim();
    const body = $("push_body").value.trim();
    const url = $("push_url").value.trim();
    const tag = $("push_tag").value.trim();
    const user_id = mode === "user" ? userInput.value.trim() : "";

    if (!title || !body) return alert("Titre et message requis.");
    if (mode === "user" && !user_id) return alert("User ID requis pour l'envoi ciblé.");

    const confirmMsg =
      mode === "all"
        ? `Envoyer cette notification à TOUS les abonnés ?\n\nTitre: ${title}\nMessage: ${body}`
        : `Envoyer à l'utilisateur:\n${user_id}\n\nTitre: ${title}\nMessage: ${body}`;

    if (!confirm(confirmMsg)) return;

    try {
      setStatus("Envoi en cours...");
      const payload = {
        title,
        body,
        url: url || null,
        tag: tag || null,
        user_id: mode === "user" ? user_id : null,
      };
      const data = await callAdminPush(payload);
      setStatus("Envoyé.");
      renderResults(data);
    } catch (e) {
      setStatus("");
      alert(e?.message || String(e));
    }
  });

  // Liste abonnés
  let lastSubscribers = [];

  function renderSubscribers(list) {
    const q = ($("subs_search").value || "").trim().toLowerCase();
    const filtered = !q
      ? list
      : list.filter(x => String(x.user_id || "").toLowerCase().includes(q));

    const el = $("subs_list");
    if (!el) return;

    if (!filtered.length) {
      el.innerHTML = `<div class="muted">Aucun abonné trouvé.</div>`;
      return;
    }

    el.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>User ID</th>
            <th>Appareils</th>
            <th>Dernier abonnement</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map(s => `
            <tr>
              <td><code>${escapeHtml(s.user_id)}</code></td>
              <td>${escapeHtml(s.endpoints)}</td>
              <td>${s.last_subscribed_at ? new Date(s.last_subscribed_at).toLocaleString("fr-FR") : "-"}</td>
              <td>
                <button class="btn btn-secondary" data-pick="${escapeHtml(s.user_id)}">Cibler</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;

    // Bouton "Cibler" => remplit user_id + switch audience
    el.querySelectorAll("[data-pick]").forEach(btn => {
      btn.addEventListener("click", () => {
        const uid = btn.getAttribute("data-pick") || "";
        $("push_audience").value = "user";
        refreshAudience();
        $("push_user_id").value = uid;
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });
  }

  $("subs_search").addEventListener("input", () => renderSubscribers(lastSubscribers));

  $("subs_refresh").addEventListener("click", async () => {
    const st = $("subs_status");
    if (st) st.textContent = "Chargement...";
    try {
      const data = await callListSubscribers();
      lastSubscribers = Array.isArray(data?.subscribers) ? data.subscribers : [];
      if (st) st.textContent = `Abonnés: ${data?.count ?? lastSubscribers.length}`;
      renderSubscribers(lastSubscribers);
    } catch (e) {
      if (st) st.textContent = "";
      alert(e?.message || String(e));
    }
  });
}

// -----------------------------
// STATS (corrigé : partages multi event_type)
// -----------------------------
async function renderStats() {
  const root = $("tab-stats");
  if (!root) return;
  root.innerHTML = premiumAdminLoading("admin", 3);

  const start = new Date();
  start.setHours(0,0,0,0);
  const startISO = start.toISOString();

  try {
    const { count: views } = await sb
      .from("analytics")
      .select("*", { count: "exact", head: true })
      .eq("event_type","visit")
      .gte("created_at", startISO);

    // ✅ Compatibilité : share / share_whatsapp / share_telegram
    const { count: shares } = await sb
      .from("analytics")
      .select("*", { count: "exact", head: true })
      .in("event_type", ["share", "share_whatsapp", "share_telegram"])
      .gte("created_at", startISO);

    const { count: clicks } = await sb
      .from("analytics")
      .select("*", { count: "exact", head: true })
      .eq("event_type","click_pronostic")
      .gte("created_at", startISO);

    const { count: vip } = await sb
      .from("analytics")
      .select("*", { count: "exact", head: true })
      .eq("event_type","vip_conversion")
      .gte("created_at", startISO);

    root.innerHTML = `
      <div class="row">
        <div class="card"><div class="muted">Visites (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${views||0}</div></div>
        <div class="card"><div class="muted">Partages (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${shares||0}</div></div>
        <div class="card"><div class="muted">Clics pronos (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${clicks||0}</div></div>
        <div class="card"><div class="muted">Conversions VIP (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${vip||0}</div></div>
      </div>
      <div class="muted" style="margin-top:10px">Astuce: harmonise les event_type dans main.js si tu veux des stats parfaites.</div>
    `;
  } catch (e) {
    root.innerHTML = `<div class="muted">Erreur stats: ${escapeHtml(e?.message || e)}</div>`;
  }
}

// -----------------------------
// PRONOSTICS (lecture seule)
// -----------------------------
async function renderPronosticsReadOnly() {
  const root = $("tab-pronostics");
  if (!root) return;

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Pronostics (lecture seule)</h3>
      <div class="row">
        <div>
          <label>Jour</label>
          <select id="pDay">
            <option value="today">Aujourd’hui</option>
            <option value="tomorrow">Demain</option>
            <option value="yesterday">Hier</option>
          </select>
        </div>
        <div>
          <label>Catégorie</label>
          <select id="pCat">
            <option value="simple">Simple</option>
            <option value="pro">Pro</option>
            <option value="vip">VIP</option>
          </select>
        </div>
      </div>
      <label>Recherche</label>
      <input id="pSearch" placeholder="équipe / ligue...">
      <div id="pList" style="margin-top:10px">${premiumAdminLoading("matches", 2)}</div>
    </div>
  `;

  const data = await fetch(`data.json?t=${Date.now()}`, { cache:"no-cache" })
    .then(r => r.json())
    .catch(() => null);

  const matches = Array.isArray(data?.matches) ? data.matches : [];

  const getDateStr = (day) => {
    const d = new Date();
    d.setUTCHours(0,0,0,0);
    if (day==="tomorrow") d.setUTCDate(d.getUTCDate()+1);
    if (day==="yesterday") d.setUTCDate(d.getUTCDate()-1);
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth()+1).padStart(2,"0");
    const dd = String(d.getUTCDate()).padStart(2,"0");
    return `${y}-${m}-${dd}`;
  };

  function render() {
    const day = $("pDay").value;
    const cat = $("pCat").value;
    const q = ($("pSearch").value||"").toLowerCase().trim();
    const targetDate = getDateStr(day);

    const list = matches.filter(m => {
      const eventDate = (m.event_date||"").slice(0,10);
      if (eventDate !== targetDate) return false;
      if ((m.category||"") !== cat) return false;
      if (!q) return true;
      const s = `${m.home_team||""} ${m.away_team||""} ${m.league||""}`.toLowerCase();
      return s.includes(q);
    });

    $("pList").innerHTML = list.length ? `
      <table>
        <thead><tr><th>Match</th><th>DC</th><th>Conf</th><th>Status</th></tr></thead>
        <tbody>
          ${list.map(m => `
            <tr>
              <td>${escapeHtml(m.home_team)} vs ${escapeHtml(m.away_team)}<div class="muted">${escapeHtml(m.league||"")}</div></td>
              <td>${escapeHtml(m.prediction?.double_chance||"-")}</td>
              <td>${escapeHtml(m.prediction?.confidence||0)}%</td>
              <td>${escapeHtml(m.status||"")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    ` : `<div class="muted">Aucun résultat.</div>`;
  }

  ["pDay","pCat","pSearch"].forEach(id => $(id).addEventListener("input", render));
  render();
}

// -----------------------------
// CMS ARTICLES
// -----------------------------
async function renderCmsArticles() {
  const root = $("tab-articles");
  if (!root) return;
  root.innerHTML = premiumAdminLoading("admin", 3);

  const { data, error } = await sb.from("cms_articles").select("*").order("updated_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${escapeHtml(error.message)}</div>`; return; }

  const rows = data || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Articles</h3>

      <div class="row">
        <div><label>Slug</label><input id="a_slug"></div>
        <div><label>Titre</label><input id="a_title"></div>
      </div>

      <label>Image URL</label><input id="a_image">
      <label>Meta description</label><input id="a_meta">
      <div class="row">
        <div><label>Catégorie</label><input id="a_category" placeholder="Analyse, actu, guide…"></div>
        <div><label>Étiquettes (virgules)</label><input id="a_tags" placeholder="Football, tactique"></div>
      </div>
      <label>Contenu</label><textarea id="a_content" rows="8"></textarea>

      <div class="row">
        <div><label>Status</label>
          <select id="a_status"><option value="draft">draft</option><option value="published">published</option></select>
        </div>
        <div><label>Actif</label>
          <select id="a_active"><option value="true">true</option><option value="false">false</option></select>
        </div>
      </div>

      <button id="a_save" class="btn btn-primary" style="margin-top:10px">Enregistrer</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste</h4>
      <div style="margin-top:10px">
        ${rows.map(a => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-id="${escapeHtml(a.id)}">
            <div style="font-weight:900">${escapeHtml(a.title)}</div>
            <div class="muted">${escapeHtml(a.slug)} • ${escapeHtml(a.status)} • active=${a.active !== false}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

  const cmsEditor = mountCmsBlockEditor({sb,textarea:$("a_content"),kind:"articles"});
  mountCmsMediaFieldPicker(sb,$("a_image"));

  const versions = mountCmsRevisionPanel({sb,table:"cms_articles",
    container:root.querySelector(".card"),onChoose:row=>setForm(row)});
  const setForm = (a) => {
    $("a_slug").value = a.slug || "";
    $("a_title").value = a.title || "";
    $("a_image").value = a.image_url || "";
    $("a_meta").value = a.meta_description || "";
    $("a_category").value = a.category || "";
    $("a_tags").value = (a.tags||[]).join(", ");
    cmsEditor.setMarkdown(a.content || "",a.id);
    $("a_status").value = a.status || "draft";
    $("a_active").value = (a.active !== false) ? "true" : "false";
    $("a_save").dataset.id = a.id;
    void versions.load(a.id);
  };

  root.querySelectorAll("[data-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const a = rows.find(x => safeIdEq(x.id, id));
      if (a) setForm(a);
    });
  });

  attachDuplicateButtons(root,"[data-id]",rows,"articles",setForm,"a_save");
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-id]")],rows,kind:"articles"});

  $("a_save").addEventListener("click", async () => {
    let cmsText;
    try { cmsText=cmsEditor.getMarkdown(); } catch(error) { alert(error.message); return; }
    const row = {
      slug: $("a_slug").value.trim(),
      title: $("a_title").value.trim(),
      image_url: $("a_image").value.trim(),
      og_image: $("a_image").value.trim(),
      meta_description: $("a_meta").value.trim(),
      category: $("a_category").value.trim(),
      tags: $("a_tags").value.split(",").map(x=>x.trim()).filter(Boolean).slice(0,12),
      content: cmsText,
      status: $("a_status").value,
      active: $("a_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: $("a_status").value === "published" ? new Date().toISOString() : null
    };
    if (!row.slug || !row.title || !row.content) return alert("Slug/Titre/Contenu requis.");

    const id = $("a_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    const { error } = await sb.from("cms_articles").upsert(payload);
    if (error) return alert(error.message);

    alert("Sauvegardé.");
    loadedTabs.delete("articles");
    await renderCmsArticles();
    loadedTabs.add("articles");
  });
}

// A copy must never reuse its source ID. No database write occurs until the admin saves it.
function attachDuplicateButtons(root,selector,rows,kind,fillForm,saveButtonId) {
  for(const card of root.querySelectorAll(selector)){
    const button=document.createElement("button");
    button.type="button";button.className="btn btn-secondary";
    button.textContent="Dupliquer en brouillon";
    button.style.marginTop="8px";
    button.addEventListener("click",event=>{
      event.preventDefault();event.stopPropagation();
      const sourceId=card.getAttribute("data-id")||card.getAttribute("data-bonus-id")||card.getAttribute("data-book-id");
      const original=rows.find(item=>safeIdEq(item.id,sourceId));
      if(!original)return;
      const draft=createCmsDraftCopy(kind,original,rows);
      fillForm(draft);
      delete $(saveButtonId).dataset.id;
      const status=document.createElement("p");
      status.className="muted";
      status.textContent="Copie préparée en brouillon inactif. Vérifie puis enregistre : l'original est intact.";
      $(saveButtonId).before(status);
      $(saveButtonId).scrollIntoView({behavior:"smooth",block:"center"});
    });
    card.appendChild(button);
  }
}

// -----------------------------
// CMS CONSEILS
// -----------------------------
async function renderCmsConseils() {
  const root = $("tab-conseils");
  if (!root) return;
  root.innerHTML = premiumAdminLoading("admin", 3);

  const { data, error } = await sb.from("cms_conseils").select("*").order("updated_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${escapeHtml(error.message)}</div>`; return; }

  const rows = data || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Conseils</h3>
      <div class="row">
        <div><label>Slug</label><input id="c_slug"></div>
        <div><label>Titre</label><input id="c_title"></div>
      </div>
      <label>Image URL</label><input id="c_image">
      <div class="row">
        <div><label>Catégorie</label><input id="c_category" placeholder="Débutants, stratégie…"></div>
        <div><label>Niveau</label><select id="c_level">
          <option value="">Non précisé</option><option value="debutant">Débutant</option>
          <option value="intermediaire">Intermédiaire</option><option value="avance">Avancé</option>
        </select></div>
      </div>
      <label>Étiquettes</label><input id="c_tags" placeholder="Conseils, sécurité">
      <label>Contenu</label><textarea id="c_content" rows="6"></textarea>

      <div class="row">
        <div><label>Status</label>
          <select id="c_status"><option value="draft">draft</option><option value="published">published</option></select>
        </div>
        <div><label>Actif</label>
          <select id="c_active"><option value="true">true</option><option value="false">false</option></select>
        </div>
      </div>

      <button id="c_save" class="btn btn-primary" style="margin-top:10px">Enregistrer</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste</h4>
      <div style="margin-top:10px">
        ${rows.map(c => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-id="${escapeHtml(c.id)}">
            <div style="font-weight:900">${escapeHtml(c.title)}</div>
            <div class="muted">${escapeHtml(c.slug)} • ${escapeHtml(c.status)} • active=${c.active !== false}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

  const cmsEditor = mountCmsBlockEditor({sb,textarea:$("c_content"),kind:"conseils"});
  mountCmsMediaFieldPicker(sb,$("c_image"));

  const versions = mountCmsRevisionPanel({sb,table:"cms_conseils",
    container:root.querySelector(".card"),onChoose:row=>setForm(row)});
  const setForm = (c) => {
    $("c_slug").value = c.slug || "";
    $("c_title").value = c.title || "";
    $("c_image").value = c.image_url || "";
    $("c_category").value = c.category || "";
    $("c_level").value = c.difficulty || "";
    $("c_tags").value = (c.tags||[]).join(", ");
    cmsEditor.setMarkdown(c.content || "",c.id);
    $("c_status").value = c.status || "draft";
    $("c_active").value = (c.active !== false) ? "true" : "false";
    $("c_save").dataset.id = c.id;
    void versions.load(c.id);
  };

  root.querySelectorAll("[data-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const c = rows.find(x => safeIdEq(x.id, id));
      if (c) setForm(c);
    });
  });

  attachDuplicateButtons(root,"[data-id]",rows,"conseils",setForm,"c_save");
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-id]")],rows,kind:"conseils"});

  $("c_save").addEventListener("click", async () => {
    let cmsText;
    try { cmsText=cmsEditor.getMarkdown(); } catch(error) { alert(error.message); return; }
    const row = {
      slug: $("c_slug").value.trim(),
      title: $("c_title").value.trim(),
      image_url: $("c_image").value.trim(),
      category: $("c_category").value.trim(),
      difficulty: $("c_level").value,
      tags: $("c_tags").value.split(",").map(x=>x.trim()).filter(Boolean).slice(0,12),
      content: cmsText,
      status: $("c_status").value,
      active: $("c_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: $("c_status").value === "published" ? new Date().toISOString() : null
    };
    if (!row.slug || !row.title || !row.content) return alert("Slug/Titre/Contenu requis.");

    const id = $("c_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    const { error } = await sb.from("cms_conseils").upsert(payload);
    if (error) return alert(error.message);

    alert("Sauvegardé.");
    loadedTabs.delete("conseils");
    await renderCmsConseils();
    loadedTabs.add("conseils");
  });
}

// -----------------------------
// BONUS + BOOKMAKERS
// -----------------------------
async function renderBonus() {
  const root = $("tab-bonus");
  if (!root) return;
  root.innerHTML = premiumAdminLoading("admin", 3);

  const [{ data: bonus, error: e1 }, { data: books, error: e2 }] = await Promise.all([
    sb.from("cms_bonus").select("*").order("updated_at",{ascending:false}).limit(50),
    sb.from("cms_bookmakers").select("*").order("updated_at",{ascending:false}).limit(50)
  ]);
  if (e1 || e2) {
    root.innerHTML = `<div class="muted">Erreur: ${escapeHtml((e1||e2).message)}</div>`;
    return;
  }

  const bonusRows = bonus || [];
  const bookRows = books || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Bonus</h3>
      <div class="row">
        <div><label>Bookmaker</label><input id="b_bookmaker"></div>
        <div><label>Titre</label><input id="b_title"></div>
      </div>
      <label>Description</label><textarea id="b_description" rows="5"></textarea>
      <div class="row">
        <div><label>Image URL</label><input id="b_image"></div>
        <div><label>Lien</label><input id="b_link"></div>
      </div>
      <div class="row">
        <div><label>Footer</label><input id="b_footer"></div>
        <div><label>Status</label>
          <select id="b_status"><option value="draft">draft</option><option value="published">published</option></select>
        </div>
      </div>
      <div class="row">
        <div><label>Date début</label><input id="b_start" type="date"></div>
        <div><label>Date fin</label><input id="b_end" type="date"></div>
      </div>
      <label>Actif</label>
      <select id="b_active"><option value="true">true</option><option value="false">false</option></select>
      <button id="b_save" class="btn btn-primary" style="margin-top:10px">Enregistrer bonus</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste bonus</h4>
      <div>
        ${bonusRows.map(b => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-bonus-id="${escapeHtml(b.id)}">
            <div style="font-weight:900">${escapeHtml(b.title)}</div>
            <div class="muted">${escapeHtml(b.bookmaker)} • ${escapeHtml(b.status)} • active=${b.active !== false}</div>
          </div>
        `).join("")}
      </div>
    </div>

    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Bookmakers</h3>
      <div class="row">
        <div><label>Nom</label><input id="bk_name"></div>
        <div><label>Logo URL</label><input id="bk_logo"></div>
      </div>
      <label>Lien</label><input id="bk_url">
      <label>Description</label><input id="bk_description">

      <div class="row">
        <div><label>Status</label>
          <select id="bk_status"><option value="published">published</option><option value="draft">draft</option></select>
        </div>
        <div><label>Actif</label>
          <select id="bk_active"><option value="true">true</option><option value="false">false</option></select>
        </div>
      </div>

      <button id="bk_save" class="btn btn-primary" style="margin-top:10px">Enregistrer bookmaker</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste bookmakers</h4>
      <div>
        ${bookRows.map(b => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-book-id="${escapeHtml(b.id)}">
            <div style="font-weight:900">${escapeHtml(b.name)}</div>
            <div class="muted">${escapeHtml(b.status)} • active=${b.active !== false}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

  mountCmsMediaFieldPicker(sb,$("b_image"));
  mountCmsMediaFieldPicker(sb,$("bk_logo"));

  const setBonus = (b) => {
    $("b_bookmaker").value = b.bookmaker || "";
    $("b_title").value = b.title || "";
    $("b_description").value = b.description || "";
    $("b_image").value = b.image_url || "";
    $("b_link").value = b.link || "";
    $("b_footer").value = b.footer || "";
    $("b_status").value = b.status || "draft";
    $("b_start").value = b.start_date || "";
    $("b_end").value = b.end_date || "";
    $("b_active").value = (b.active !== false) ? "true" : "false";
    $("b_save").dataset.id = b.id;
  };

  const setBook = (b) => {
    $("bk_name").value = b.name || "";
    $("bk_logo").value = b.logo || "";
    $("bk_url").value = b.url || "";
    $("bk_description").value = b.description || "";
    $("bk_status").value = b.status || "published";
    $("bk_active").value = (b.active !== false) ? "true" : "false";
    $("bk_save").dataset.id = b.id;
  };

  root.querySelectorAll("[data-bonus-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-bonus-id");
      const b = bonusRows.find(x => safeIdEq(x.id, id));
      if (b) setBonus(b);
    });
  });

  root.querySelectorAll("[data-book-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-book-id");
      const b = bookRows.find(x => safeIdEq(x.id, id));
      if (b) setBook(b);
    });
  });

  attachDuplicateButtons(root,"[data-bonus-id]",bonusRows,"bonus",setBonus,"b_save");
  attachDuplicateButtons(root,"[data-book-id]",bookRows,"bookmakers",setBook,"bk_save");
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-bonus-id]")],rows:bonusRows,kind:"bonus",showCategory:false});
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-book-id]")],rows:bookRows,kind:"bookmakers",showCategory:false});

  $("b_save").addEventListener("click", async () => {
    const row = {
      bookmaker: $("b_bookmaker").value.trim(),
      title: $("b_title").value.trim(),
      description: $("b_description").value.trim(),
      image_url: $("b_image").value.trim(),
      link: $("b_link").value.trim(),
      footer: $("b_footer").value.trim(),
      start_date: $("b_start").value || null,
      end_date: $("b_end").value || null,
      status: $("b_status").value,
      active: $("b_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: $("b_status").value === "published" ? new Date().toISOString() : null
    };
    if (!row.bookmaker || !row.title || !row.description) return alert("Bookmaker/Titre/Description requis.");

    const id = $("b_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    const { error } = await sb.from("cms_bonus").upsert(payload);
    if (error) return alert(error.message);

    alert("Bonus sauvegardé.");
    loadedTabs.delete("bonus");
    await renderBonus();
    loadedTabs.add("bonus");
  });

  $("bk_save").addEventListener("click", async () => {
    const row = {
      name: $("bk_name").value.trim(),
      logo: $("bk_logo").value.trim(),
      url: $("bk_url").value.trim(),
      description: $("bk_description").value.trim(),
      status: $("bk_status").value,
      active: $("bk_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: $("bk_status").value === "published" ? new Date().toISOString() : null
    };
    if (!row.name) return alert("Nom requis.");

    const id = $("bk_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    const { error } = await sb.from("cms_bookmakers").upsert(payload);
    if (error) return alert(error.message);

    alert("Bookmaker sauvegardé.");
    loadedTabs.delete("bonus");
    await renderBonus();
    loadedTabs.add("bonus");
  });
}

// -----------------------------
// INFOS
// -----------------------------
async function renderInfos() {
  const root = $("tab-infos");
  if (!root) return;

  root.innerHTML = premiumAdminLoading("admin", 3);
  const { data, error } = await sb.from("cms_infos").select("*").order("updated_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${escapeHtml(error.message)}</div>`; return; }

  const rows = data || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Infos</h3>
      <label>Titre</label><input id="i_title">
      <div class="row"><div><label>Catégorie</label><input id="i_category"></div>
        <div><label>Image</label><input id="i_image"></div></div>
      <label>Contenu</label><textarea id="i_content" rows="6"></textarea>
      <div class="row">
        <div><label>Status</label>
          <select id="i_status"><option value="draft">draft</option><option value="published">published</option></select>
        </div>
        <div><label>Actif</label>
          <select id="i_active"><option value="true">true</option><option value="false">false</option></select>
        </div>
      </div>
      <button id="i_save" class="btn btn-primary" style="margin-top:10px">Enregistrer</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Liste</h4>
      ${rows.map(i => `
        <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-id="${escapeHtml(i.id)}">
          <div style="font-weight:900">${escapeHtml(i.title)}</div>
          <div class="muted">${escapeHtml(i.status)} • active=${i.active !== false}</div>
        </div>
      `).join("")}
    </div>
  `;

  const cmsEditor = mountCmsBlockEditor({sb,textarea:$("i_content"),kind:"infos"});
  mountCmsMediaFieldPicker(sb,$("i_image"));

  const versions = mountCmsRevisionPanel({sb,table:"cms_infos",
    container:root.querySelector(".card"),onChoose:row=>setForm(row)});
  const setForm = (i) => {
    $("i_title").value = i.title || "";
    $("i_category").value = i.category || "";
    $("i_image").value = i.image_url || "";
    cmsEditor.setMarkdown(i.content || "",i.id);
    $("i_status").value = i.status || "draft";
    $("i_active").value = (i.active !== false) ? "true" : "false";
    $("i_save").dataset.id = i.id;
    void versions.load(i.id);
  };

  root.querySelectorAll("[data-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const i = rows.find(x => safeIdEq(x.id, id));
      if (i) setForm(i);
    });
  });

  attachDuplicateButtons(root,"[data-id]",rows,"infos",setForm,"i_save");
  mountCmsListFilters({root,cards:[...root.querySelectorAll("[data-id]")],rows,kind:"informations"});

  $("i_save").addEventListener("click", async () => {
    let cmsText;
    try { cmsText=cmsEditor.getMarkdown(); } catch(error) { alert(error.message); return; }
    const row = {
      title: $("i_title").value.trim(),
      category: $("i_category").value.trim(),
      image_url: $("i_image").value.trim(),
      content: cmsText,
      status: $("i_status").value,
      active: $("i_active").value === "true",
      updated_at: new Date().toISOString(),
      published_at: $("i_status").value === "published" ? new Date().toISOString() : null
    };
    if (!row.title || !row.content) return alert("Titre/Contenu requis.");

    const id = $("i_save").dataset.id;
    const payload = id ? { ...row, id } : row;

    const { error } = await sb.from("cms_infos").upsert(payload);
    if (error) return alert(error.message);

    alert("Info sauvegardée.");
    loadedTabs.delete("infos");
    await renderInfos();
    loadedTabs.add("infos");
  });
}

// -----------------------------
// CMS MEDIA LIBRARY
// -----------------------------
async function renderMediaTab(){
  const root=$("tab-media");if(!root)return;
  root.replaceChildren();
  const intro=document.createElement("div");
  intro.className="card";
  const h=document.createElement("h3");h.textContent="Médiathèque";
  const p=document.createElement("p");p.className="muted";
  p.textContent="Importer, rechercher et réutiliser les photos ou vidéos dans les publications. Attention : les fichiers sont hébergés dans un bucket public ; toute personne possédant leur URL peut les consulter, même avant publication. Les brouillons CMS, eux, ne sont pas publiés automatiquement.";
  const selected=document.createElement("p");selected.setAttribute("role","status");
  intro.append(h,p,selected);root.appendChild(intro);
  mountCmsMediaPicker(sb,intro,media=>{
    selected.textContent="Lien du média sélectionné : "+media.url;
    if(navigator.clipboard?.writeText)void navigator.clipboard.writeText(media.url).catch(()=>{});
  });
}

// -----------------------------
// VIP
// -----------------------------
async function renderVip() {
  const root = $("tab-vip");
  if (!root) return;

  root.innerHTML = premiumAdminLoading("admin", 3);
  const { data, error } = await sb.from("vip_access").select("*").order("expires_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${escapeHtml(error.message)}</div>`; return; }

  const rows = data || [];

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">VIP (reset expiration)</h3>

      <div class="row">
        <div><label>User ID (MX-xxxx)</label><input id="v_user" placeholder="MX-..."></div>
        <div><label>IP (optionnel)</label><input id="v_ip" placeholder="1.2.3.4"></div>
      </div>

      <label>Durée (jours)</label><input id="v_days" type="number" min="1" value="30">

      <button id="v_reset" class="btn btn-primary" style="margin-top:10px">Créer / Réinitialiser VIP</button>

      <h4 style="margin:18px 0 8px;color:#D4AF37">Actifs / Historique</h4>

      <table>
        <thead><tr><th>User</th><th>Code</th><th>Expire</th><th>Actif</th><th>Action</th></tr></thead>
        <tbody>
          ${rows.map(v => `
            <tr>
              <td>${escapeHtml(v.user_id)}</td>
              <td>${escapeHtml(v.code)}</td>
              <td>${v.expires_at ? new Date(v.expires_at).toLocaleString("fr-FR") : "-"}</td>
              <td>${v.active ? "oui" : "non"}</td>
              <td><button class="btn btn-secondary" data-revoke="${escapeHtml(v.user_id)}">Désactiver</button></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  $("v_reset").addEventListener("click", async () => {
    const uid = $("v_user").value.trim();
    const ip = $("v_ip").value.trim();
    const days = parseInt($("v_days").value, 10) || 30;
    if (!uid) return alert("User ID requis");

    const { data, error } = await sb.rpc("admin_reset_vip", {
      p_user_id: uid,
      p_ip: ip,
      p_duration_days: days
    });

    if (error) return alert(error.message);

    const row = Array.isArray(data) ? data[0] : data;
    alert(`VIP OK. Code: ${row?.code} / Expire: ${row?.expires_at}`);
    loadedTabs.delete("vip");
    await renderVip();
    loadedTabs.add("vip");
  });

  root.querySelectorAll("[data-revoke]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const uid = btn.getAttribute("data-revoke");
      if (!confirm("Désactiver VIP ?")) return;

      const { error } = await sb.rpc("admin_revoke_vip", { p_user_id: uid });
      if (error) return alert(error.message);

      loadedTabs.delete("vip");
      await renderVip();
      loadedTabs.add("vip");
    });
  });
}

// -----------------------------
// HEALTH
// -----------------------------
async function renderHealth() {
  const root = $("tab-health");
  if (!root) return;

  const { data, error } = await sb.from("cron_runs").select("*").order("last_run_at",{ascending:false});
  if (error) { root.innerHTML = `<div class="muted">${escapeHtml(error.message)}</div>`; return; }

  const rows = (data || []).map(r => {
    const meta = r.meta || {};
    const summary =
      r.name === "live_refresh"
        ? `matches=${meta.matches_live ?? 0}, created=${meta.predictions_created ?? 0}, updated=${meta.predictions_updated ?? 0}`
        : `validated=${meta.validated ?? 0}, skipped=${meta.skipped ?? 0}`;

    return `
      <tr>
        <td>${escapeHtml(r.name)}</td>
        <td>${r.last_run_at ? new Date(r.last_run_at).toLocaleString("fr-FR") : "-"}</td>
        <td>${r.last_ok ? "oui" : "non"}</td>
        <td>
          <div class="muted">${escapeHtml(summary)}</div>
          <button class="btn btn-secondary" data-meta='${encodeURIComponent(JSON.stringify(meta))}'>Voir</button>
        </td>
      </tr>
    `;
  }).join("");

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Santé CRON</h3>
      <table>
        <thead><tr><th>Nom</th><th>Dernière exécution</th><th>OK</th><th>Meta</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>

      <div id="metaModal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,.7); padding:20px; z-index:9999;">
        <div style="max-width:900px; margin:0 auto; background:#1A1A1A; border:1px solid #D4AF37; border-radius:16px; padding:16px;">
          <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
            <div style="font-weight:900; color:#D4AF37">Meta</div>
            <button id="closeMeta" class="btn btn-secondary">Fermer</button>
          </div>
          <pre id="metaContent" style="margin-top:12px; max-height:70vh; overflow:auto; white-space:pre-wrap; color:#ddd;"></pre>
        </div>
      </div>
    </div>
  `;

  const modal = $("metaModal");
  const pre = $("metaContent");
  $("closeMeta").onclick = () => (modal.style.display = "none");

  root.querySelectorAll("[data-meta]").forEach(btn => {
    btn.addEventListener("click", () => {
      const meta = JSON.parse(decodeURIComponent(btn.getAttribute("data-meta")));
      pre.textContent = JSON.stringify(meta, null, 2);
      modal.style.display = "block";
    });
  });
}

// -----------------------------
// AUDIT
// -----------------------------
async function renderAudit() {
  const root = $("tab-audit");
  if (!root) return;

  const { data, error } = await sb.from("audit_log").select("*").order("created_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">${escapeHtml(error.message)}</div>`; return; }

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Audit log</h3>
      <table>
        <thead><tr><th>Date</th><th>Action</th><th>Détails</th></tr></thead>
        <tbody>
          ${(data||[]).map(a => `
            <tr>
              <td>${new Date(a.created_at).toLocaleString("fr-FR")}</td>
              <td>${escapeHtml(a.action)}</td>
              <td><pre style="white-space:pre-wrap" class="muted">${escapeHtml(JSON.stringify(a.details||{}, null, 2))}</pre></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

// -----------------------------

async function cmsAdminRequest(operation,extra={}) {
  const session=(await sb.auth.getSession()).data.session;
  if(!session) throw new Error("Session administrateur expirée");
  const response=await fetch(`${adminApiUrl}/publish`,{
    method:"POST",
    headers:{"Content-Type":"application/json","Authorization":`Bearer ${session.access_token}`},
    body:JSON.stringify({operation,...extra})
  });
  const data=await response.json().catch(()=>({}));
  if(!response.ok) throw new Error(data.error||`Erreur HTTP ${response.status}`);
  return data;
}
function cmsDom(tag,text="",className="") {
  const node=document.createElement(tag);node.textContent=text;
  if(className)node.className=className;
  return node;
}
async function cmsCheckCommit(commit,root) {
  root.textContent="Vérification du déploiement GitHub Pages…";
  try {
    const s=await cmsAdminRequest("status",{commit});
    const map={deployed:"Déploiement réussi",pending:"Déploiement en cours",
      failed:"Déploiement échoué",unknown:"Statut de déploiement inconnu"};
    root.textContent=(map[s.deployment]||"Statut non confirmé")+" — "+commit.slice(0,12)+
      (s.is_current?" (version courante)":" (une autre version est courante)");
    if(s.workflow_url&&/^https:\/\/github\.com\//.test(s.workflow_url)){
      const a=cmsDom("a"," — Voir le workflow");a.href=s.workflow_url;a.target="_blank";a.rel="noopener noreferrer";
      root.appendChild(a);
    }
  }catch(error){root.textContent="Impossible de vérifier : "+error.message;}
}
async function cmsShowPreview(entry,root) {
  root.replaceChildren(cmsDom("p","Préparation de la comparaison…"));
  try{
    const data=await cmsAdminRequest("preview_restore",{version_id:entry.id});
    const p=data.preview;
    root.replaceChildren(cmsDom("h4","Prévisualisation du retour arrière"));
    root.appendChild(cmsDom("p","Source : "+p.target_commit.slice(0,12)+" | Branche actuelle : "+p.current_head.slice(0,12)));
    const table=cmsDom("table"),body=cmsDom("tbody");
    const head=cmsDom("tr");
    for(const name of ["Fichier","Actuel","Version choisie","Ajoutés","Supprimés","Modifiés"]){
      head.appendChild(cmsDom("th",name));
    }
    table.appendChild(head);
    for(const [file,change] of Object.entries(p.changes||{})){
      const tr=cmsDom("tr");
      for(const value of [file,change.before,change.after,change.added,change.removed,change.modified]){
        tr.appendChild(cmsDom("td",String(value)));
      }
      body.appendChild(tr);
      const examples=[...(change.samples?.added||[]),...(change.samples?.removed||[]),...(change.samples?.modified||[])];
      if(examples.length)root.appendChild(cmsDom("p",file+" — Exemples : "+examples.join(", "),"muted"));
    }
    table.appendChild(body);root.appendChild(table);
    const changes=Object.values(p.changes||{}).some(c=>c.different);
    if(!changes){root.appendChild(cmsDom("p","Ces fichiers sont identiques. Aucune restauration nécessaire."));return;}
    const warning=cmsDom("p","Attention : seuls les cinq fichiers de contenu seront restaurés. L'historique Git et la base Neon restent inchangés.");
    root.appendChild(warning);
    const restore=cmsDom("button","Restaurer cette version","btn btn-secondary");restore.type="button";
    restore.addEventListener("click",async()=>{
      if(!window.confirm("Créer un nouveau commit qui remplace les cinq JSON par cette version historique ?"))return;
      if(window.prompt("Confirmation : écris exactement RESTAURER")!=="RESTAURER")return;
      restore.disabled=true;
      try{
        const result=await cmsAdminRequest("restore",{version_id:p.version_id,expected_head:p.current_head,
          preview_expires:p.preview_expires,preview_signature:p.preview_signature,confirm:"RESTAURER"});
        root.replaceChildren(cmsDom("p","Commit de restauration créé : "+result.github_commit.slice(0,12)+". Déploiement à confirmer."));
        const check=cmsDom("button","Vérifier la mise en ligne","btn btn-secondary");check.type="button";
        check.addEventListener("click",()=>void cmsCheckCommit(result.github_commit,root));
        root.appendChild(check);
      }catch(error){
        root.appendChild(cmsDom("p","Restauration refusée ou échouée : "+error.message));
        restore.disabled=false;
      }
    });
    root.appendChild(restore);
  }catch(error){root.replaceChildren(cmsDom("p","Impossible de prévisualiser : "+error.message));}
}
async function cmsLoadHistory(root){
  root.replaceChildren(cmsDom("p","Chargement de l'historique…"));
  try{
    const data=await cmsAdminRequest("history");
    root.replaceChildren(cmsDom("h3","Historique des publications"));
    if(!(data.versions||[]).length){
      root.appendChild(cmsDom("p","Aucune version enregistrée pour le moment. Une première publication créera un historique."));return;
    }
    for(const entry of data.versions){
      const row=cmsDom("div");row.style.cssText="border-bottom:1px solid #444;padding:8px 0";
      row.appendChild(cmsDom("span",new Date(entry.date).toLocaleString("fr-FR")+" — "+entry.github_commit.slice(0,12)+" — "+entry.status+" "));
      const preview=cmsDom("button","Comparer","btn btn-secondary");preview.type="button";
      const status=cmsDom("button","Statut","btn btn-secondary");status.type="button";
      const detail=cmsDom("div");
      preview.addEventListener("click",()=>void cmsShowPreview(entry,detail));
      status.addEventListener("click",()=>void cmsCheckCommit(entry.github_commit,detail));
      row.append(preview,status,detail);root.appendChild(row);
    }
  }catch(error){root.replaceChildren(cmsDom("p","Historique indisponible : "+error.message));}
}
function cmsInstallHistory(){
  if($("cms-history-btn"))return;
  const area=$("btnPublish")?.parentElement;if(!area)return;
  const button=cmsDom("button","Historique / restaurer","btn btn-secondary");
  button.id="cms-history-btn";button.type="button";
  const root=cmsDom("div");root.id="cms-history-root";
  root.style.cssText="width:100%;padding:10px 0";
  button.addEventListener("click",()=>void cmsLoadHistory(root));
  area.append(button,root);
}

// PUBLISH (corrigé headers)
// -----------------------------
async function publishNow() {
  if(publishBusy)return;
  publishBusy=true;
  setBtnDisabled("btnPublish",true);
  let panel=$("cms-publish-result");
  if(!panel){
    panel=cmsDom("div");
    panel.id="cms-publish-result";
    panel.setAttribute("role","status");
    panel.setAttribute("aria-live","polite");
    panel.style.cssText="padding:12px;margin:12px 0;border:1px solid #666;border-radius:10px";
    $("btnPublish").parentElement.appendChild(panel);
  }
  panel.textContent="Prévisualisation de la publication en cours…";
  try{
    const {preview}=await cmsAdminRequest("preflight");
    if(!preview?.has_changes){
      panel.textContent="Aucun changement à publier : les cinq fichiers GitHub sont déjà à jour.";
      return;
    }
    const lines=Object.entries(preview.changes).filter(([,data])=>data.different)
      .map(([path,data])=>path+" : "+data.before+" → "+data.after).join("\n");
    panel.textContent="Modifications proposées :\n"+lines;
    panel.style.whiteSpace="pre-line";
    if(!window.confirm("Publier les modifications suivantes sur le site ?\n\n"+lines)){
      panel.textContent="Publication annulée : aucun commit créé.";
      return;
    }
    let acknowledge_empty;
    if(preview.emptied_files?.length){
      const files=preview.emptied_files.join(", ");
      if(window.prompt("Attention : les fichiers suivants vont être vidés : "+files+
        "\nPour confirmer, tape exactement PUBLIER VIDE")!=="PUBLIER VIDE"){
        panel.textContent="Publication annulée : suppression des contenus non confirmée.";
        return;
      }
      acknowledge_empty="PUBLIER VIDE";
    }
    panel.textContent="Publication préparée : création du commit GitHub…";
    const data=await cmsAdminRequest("publish",{
      expected_head:preview.current_head,
      preflight_expires:preview.preflight_expires,
      preflight_signature:preview.preflight_signature,
      acknowledge_empty
    });
    if(data.skipped){
      panel.textContent="Aucun changement à publier : aucun commit créé.";
      return;
    }
    const commit=data?.github_commit;
    if(!commit){panel.textContent="Le serveur n'a pas retourné de commit : mise en ligne non confirmée.";return;}
    panel.textContent="Commit GitHub créé : "+commit.slice(0,12)+". Mise en ligne non confirmée.";
    const check=cmsDom("button","Vérifier le déploiement","btn btn-secondary");
    check.type="button";check.style.marginLeft="10px";
    let pendingTimer=null,attempts=0;
    async function verify(){
      if(pendingTimer!==null){clearTimeout(pendingTimer);pendingTimer=null;}
      const output=cmsDom("span","Vérification du déploiement…");
      panel.replaceChildren(output,check);
      try{
        const value=await cmsAdminRequest("status",{commit});
        const labels={deployed:"Déploiement confirmé",pending:"Déploiement en cours",
          failed:"Déploiement échoué",unknown:"Déploiement non confirmé"};
        output.textContent=(labels[value.deployment]||"Déploiement non confirmé")+" — "+commit.slice(0,12)+
          (value.is_current?" (commit actuel)":" (version antérieure)");
        if(value.workflow_url&&/^https:\/\/github\.com\//.test(value.workflow_url)){
          const url=cmsDom("a"," — Détails GitHub");url.href=value.workflow_url;
          url.rel="noopener noreferrer";url.target="_blank";output.appendChild(url);
        }
        if(value.deployment==="pending"&&attempts++<12)
          pendingTimer=setTimeout(()=>void verify(),12000);
      }catch(error){output.textContent="Vérification indisponible : "+error.message;}
    }
    check.addEventListener("click",()=>void verify());
    panel.appendChild(check);
    void verify();
    const history=$("cms-history-root");
    if(history?.childElementCount)void cmsLoadHistory(history);
  }catch(error){
    panel.textContent="Erreur de publication (vérifier l'historique avant de réessayer) : "+error.message;
  }finally{
    publishBusy=false;
    setBtnDisabled("btnPublish",false);
  }
}

// -----------------------------
// LOGIN FLOW
// -----------------------------
async function afterLogin() {
  if (!(await isAdmin())) {
    await sb.auth.signOut();
    setLoginMsg("Compte non admin.");
    return;
  }

  $("loginCard").style.display = "none";
  $("app").style.display = "block";
  cmsInstallHistory();
  await initAdminMfaControl(sb, $("btnLogout")?.parentElement);

  const user = (await sb.auth.getUser()).data.user;
  $("who").textContent = user?.email || user?.id || "";

  // Only load the selected screen, and preserve deep links on reload.
  const route=location.hash.slice(1);
  await showTab(TAB_NAMES.includes(route)?route:"overview");
}

// -----------------------------
// EVENTS
// -----------------------------
tabs().forEach(btn => btn.addEventListener("click", () => void showTab(btn.dataset.tab)));
window.addEventListener("hashchange",()=>{if($("app").style.display!=="none")void showTab(location.hash.slice(1))});

$("loginForm").addEventListener("submit", async event => {
  event.preventDefault();
  if ($("btnLogin").disabled) return;
  $("btnLogin").disabled=true;
  setLoginMsg("Connexion...");
  const email = $("email").value.trim();
  const password = $("password").value;

  const { error } = await sb.auth.signInWithPassword({ email, password });
  if (error) { setLoginMsg(error.message); $("btnLogin").disabled=false; return; }

  setLoginMsg("");
  try { await afterLogin(); }
  finally { $("btnLogin").disabled=false; }
});

$("btnLogout").addEventListener("click", async () => {
  await sb.auth.signOut();
  location.reload();
});

$("btnPublish").addEventListener("click", publishNow);

(async () => {
  const session = (await sb.auth.getSession()).data.session;
  if (session) await afterLogin();
})();