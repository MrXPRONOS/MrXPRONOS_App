import { supabaseUrl, supabaseAnonKey } from "./config.js";

const sb = window.supabase.createClient(supabaseUrl, supabaseAnonKey);

const $ = (id) => document.getElementById(id);
const tabs = () => Array.from(document.querySelectorAll(".tab"));

function showTab(name) {
  tabs().forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  ["stats","pronostics","articles","conseils","vip","health","audit"].forEach(n => {
    $(`tab-${n}`).style.display = (n === name) ? "block" : "none";
  });
}

tabs().forEach(btn => btn.addEventListener("click", () => showTab(btn.dataset.tab)));

async function isAdmin() {
  const { data, error } = await sb.rpc("is_admin");
  if (error) return false;
  return data === true;
}

async function renderStats() {
  const root = $("tab-stats");
  root.innerHTML = `<div class="muted">Chargement stats...</div>`;

  const start = new Date(); start.setHours(0,0,0,0);
  const startISO = start.toISOString();

  // VRAI : analytics
  const { count: views } = await sb.from("analytics").select("*", { count: "exact", head: true })
    .eq("event_type","visit").gte("created_at", startISO);

  const { count: shares } = await sb.from("analytics").select("*", { count: "exact", head: true })
    .eq("event_type","share").gte("created_at", startISO);

  const { count: clicks } = await sb.from("analytics").select("*", { count: "exact", head: true })
    .eq("event_type","click_pronostic").gte("created_at", startISO);

  const { count: vip } = await sb.from("analytics").select("*", { count: "exact", head: true })
    .eq("event_type","vip_conversion").gte("created_at", startISO);

  root.innerHTML = `
    <div class="row">
      <div class="card"><div class="muted">Visites (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${views||0}</div></div>
      <div class="card"><div class="muted">Partages (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${shares||0}</div></div>
      <div class="card"><div class="muted">Clics pronos (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${clicks||0}</div></div>
      <div class="card"><div class="muted">Conversions VIP (aujourd’hui)</div><div style="font-size:28px;font-weight:900;color:#D4AF37">${vip||0}</div></div>
    </div>
  `;
}

async function renderPronosticsReadOnly() {
  const root = $("tab-pronostics");
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
      <div id="pList" class="muted" style="margin-top:10px">Chargement...</div>
    </div>
  `;

  const data = await fetch(`data.json?t=${Date.now()}`, { cache:"no-cache" }).then(r => r.json()).catch(() => null);
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
    const day = document.getElementById("pDay").value;
    const cat = document.getElementById("pCat").value;
    const q = (document.getElementById("pSearch").value||"").toLowerCase().trim();
    const targetDate = getDateStr(day);

    const list = matches.filter(m => {
      const eventDate = (m.event_date||"").slice(0,10);
      if (eventDate !== targetDate) return false;
      if ((m.category||"") !== cat) return false;
      if (!q) return true;
      const s = `${m.home_team||""} ${m.away_team||""} ${m.league||""}`.toLowerCase();
      return s.includes(q);
    });

    document.getElementById("pList").innerHTML = list.length ? `
      <table>
        <thead><tr><th>Match</th><th>DC</th><th>Conf</th><th>Status</th></tr></thead>
        <tbody>
        ${list.map(m => `
          <tr>
            <td>${m.home_team} vs ${m.away_team}<div class="muted">${m.league||""}</div></td>
            <td>${m.prediction?.double_chance||"-"}</td>
            <td>${m.prediction?.confidence||0}%</td>
            <td>${m.status||""}</td>
          </tr>
        `).join("")}
        </tbody>
      </table>
    ` : `<div class="muted">Aucun résultat.</div>`;
  }

  ["pDay","pCat","pSearch"].forEach(id => document.getElementById(id).addEventListener("input", render));
  render();
}

async function renderCmsArticles() {
  const root = $("tab-articles");
  root.innerHTML = `<div class="muted">Chargement...</div>`;

  const { data, error } = await sb.from("cms_articles").select("*").order("updated_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${error.message}</div>`; return; }

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Articles (DB → Publish → articles.json)</h3>

      <div class="row">
        <div><label>Slug</label><input id="a_slug" placeholder="ex: psg-om"></div>
        <div><label>Titre</label><input id="a_title" placeholder="Titre..."></div>
      </div>
      <label>Image URL</label><input id="a_image" placeholder="https://...">
      <label>Meta description</label><input id="a_meta" placeholder="160 chars...">
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
      <div class="muted">Clique un item pour le charger dans le formulaire.</div>
      <div style="margin-top:10px">
        ${data.map(a => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-id="${a.id}">
            <div style="font-weight:900">${a.title}</div>
            <div class="muted">${a.slug} • ${a.status} • active=${a.active}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

  const setForm = (a) => {
    $("a_slug").value = a.slug || "";
    $("a_title").value = a.title || "";
    $("a_image").value = a.image_url || "";
    $("a_meta").value = a.meta_description || "";
    $("a_content").value = a.content || "";
    $("a_status").value = a.status || "draft";
    $("a_active").value = (a.active !== false) ? "true" : "false";
    $("a_save").dataset.id = a.id;
  };

  root.querySelectorAll("[data-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const a = data.find(x => x.id === id);
      if (a) setForm(a);
    });
  });

  $("a_save").addEventListener("click", async () => {
    const row = {
      slug: $("a_slug").value.trim(),
      title: $("a_title").value.trim(),
      image_url: $("a_image").value.trim(),
      og_image: $("a_image").value.trim(),
      meta_description: $("a_meta").value.trim(),
      content: $("a_content").value,
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
    await renderCmsArticles();
  });
}

async function renderCmsConseils() {
  const root = $("tab-conseils");
  root.innerHTML = `<div class="muted">Chargement...</div>`;

  const { data, error } = await sb.from("cms_conseils").select("*").order("updated_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${error.message}</div>`; return; }

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Conseils (DB → Publish → conseils.json)</h3>

      <div class="row">
        <div><label>Slug</label><input id="c_slug"></div>
        <div><label>Titre</label><input id="c_title"></div>
      </div>
      <label>Image URL</label><input id="c_image">
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
        ${data.map(c => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-id="${c.id}">
            <div style="font-weight:900">${c.title}</div>
            <div class="muted">${c.slug} • ${c.status} • active=${c.active}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

  const setForm = (c) => {
    $("c_slug").value = c.slug || "";
    $("c_title").value = c.title || "";
    $("c_image").value = c.image_url || "";
    $("c_content").value = c.content || "";
    $("c_status").value = c.status || "draft";
    $("c_active").value = (c.active !== false) ? "true" : "false";
    $("c_save").dataset.id = c.id;
  };

  root.querySelectorAll("[data-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const c = data.find(x => x.id === id);
      if (c) setForm(c);
    });
  });

  $("c_save").addEventListener("click", async () => {
    const row = {
      slug: $("c_slug").value.trim(),
      title: $("c_title").value.trim(),
      image_url: $("c_image").value.trim(),
      content: $("c_content").value,
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
    await renderCmsConseils();
  });
}

async function renderVip() {
  const root = $("tab-vip");
  root.innerHTML = `<div class="muted">Chargement...</div>`;

  const { data, error } = await sb.from("vip_access").select("*").order("expires_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${error.message}</div>`; return; }

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
          ${(data||[]).map(v => `
            <tr>
              <td>${v.user_id}</td>
              <td>${v.code}</td>
              <td>${new Date(v.expires_at).toLocaleString("fr-FR")}</td>
              <td>${v.active ? "oui" : "non"}</td>
              <td>
                <button class="btn btn-secondary" data-revoke="${v.user_id}">Désactiver</button>
              </td>
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

    const { data, error } = await sb.rpc("admin_reset_vip", { p_user_id: uid, p_ip: ip, p_duration_days: days });
    if (error) return alert(error.message);

    alert(`VIP OK. Code: ${data?.[0]?.code} / Expire: ${data?.[0]?.expires_at}`);
    await renderVip();
  });

  root.querySelectorAll("[data-revoke]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const uid = btn.getAttribute("data-revoke");
      if (!confirm("Désactiver VIP ?")) return;
      const { error } = await sb.rpc("admin_revoke_vip", { p_user_id: uid });
      if (error) return alert(error.message);
      await renderVip();
    });
  });
}

async function renderHealth() {
  const root = $("tab-health");
  const { data, error } = await sb.from("cron_runs").select("*").order("last_run_at",{ascending:false});
  if (error) { root.innerHTML = `<div class="muted">${error.message}</div>`; return; }

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Santé CRON</h3>
      <table>
        <thead><tr><th>Nom</th><th>Dernière exécution</th><th>OK</th><th>Meta</th></tr></thead>
        <tbody>
          ${(data||[]).map(r => `
            <tr>
              <td>${r.name}</td>
              <td>${r.last_run_at ? new Date(r.last_run_at).toLocaleString("fr-FR") : "-"}</td>
              <td>${r.last_ok ? "oui" : "non"}</td>
              <td><pre style="white-space:pre-wrap" class="muted">${JSON.stringify(r.meta||{}, null, 2)}</pre></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      <div class="muted">Si live_refresh ne bouge pas chaque minute → cron-job.org n’appelle pas /live/refresh.</div>
    </div>
  `;
}

async function renderAudit() {
  const root = $("tab-audit");
  const { data, error } = await sb.from("audit_log").select("*").order("created_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">${error.message}</div>`; return; }

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Audit log</h3>
      <table>
        <thead><tr><th>Date</th><th>Action</th><th>Détails</th></tr></thead>
        <tbody>
          ${(data||[]).map(a => `
            <tr>
              <td>${new Date(a.created_at).toLocaleString("fr-FR")}</td>
              <td>${a.action}</td>
              <td><pre style="white-space:pre-wrap" class="muted">${JSON.stringify(a.details||{}, null, 2)}</pre></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function publishNow() {
  const session = (await sb.auth.getSession()).data.session;
  if (!session) return alert("Session expirée.");

  const res = await fetch(`${supabaseUrl}/functions/v1/publish`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${session.access_token}`,
    },
    body: JSON.stringify({}),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) return alert(data?.error || "Erreur publish");
  alert(`Publié. Articles=${data.counts.articles} / Conseils=${data.counts.conseils}`);
}

async function afterLogin() {
  if (!(await isAdmin())) {
    await sb.auth.signOut();
    $("loginMsg").textContent = "Compte non admin.";
    return;
  }

  $("loginCard").style.display = "none";
  $("app").style.display = "block";

  const user = (await sb.auth.getUser()).data.user;
  $("who").textContent = user?.email || user?.id || "";

  await renderStats();
  await renderPronosticsReadOnly();
  await renderCmsArticles();
  await renderCmsConseils();
  await renderVip();
  await renderHealth();
  await renderAudit();
}

$("btnLogin").addEventListener("click", async () => {
  $("loginMsg").textContent = "Connexion...";
  const email = $("email").value.trim();
  const password = $("password").value;
  const { error } = await sb.auth.signInWithPassword({ email, password });
  if (error) { $("loginMsg").textContent = error.message; return; }
  $("loginMsg").textContent = "";
  await afterLogin();
});

$("btnLogout").addEventListener("click", async () => {
  await sb.auth.signOut();
  location.reload();
});

$("btnPublish").addEventListener("click", publishNow);

// auto session
(async () => {
  const session = (await sb.auth.getSession()).data.session;
  if (session) await afterLogin();
})();