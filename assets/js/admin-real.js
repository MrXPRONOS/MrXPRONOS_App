import { supabaseUrl, supabaseAnonKey } from "./config.js";

const sb = window.supabase.createClient(supabaseUrl, supabaseAnonKey);

const $ = (id) => document.getElementById(id);
const tabs = () => Array.from(document.querySelectorAll(".tab"));

function showTab(name) {
  tabs().forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  ["stats","pronostics","articles","conseils","bonus","infos","vip","health","audit"].forEach(n => {
    const el = $(`tab-${n}`);
    if (el) el.style.display = (n === name) ? "block" : "none";
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

  const start = new Date();
  start.setHours(0,0,0,0);
  const startISO = start.toISOString();

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
      <h3 style="margin:0 0 10px;color:#D4AF37">Articles</h3>
      <div class="row">
        <div><label>Slug</label><input id="a_slug"></div>
        <div><label>Titre</label><input id="a_title"></div>
      </div>
      <label>Image URL</label><input id="a_image">
      <label>Meta description</label><input id="a_meta">
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
      <h3 style="margin:0 0 10px;color:#D4AF37">Conseils</h3>

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

async function renderBonus() {
  const root = $("tab-bonus");
  root.innerHTML = `<div class="muted">Chargement...</div>`;

  const [{ data: bonus, error: e1 }, { data: books, error: e2 }] = await Promise.all([
    sb.from("cms_bonus").select("*").order("updated_at",{ascending:false}).limit(50),
    sb.from("cms_bookmakers").select("*").order("updated_at",{ascending:false}).limit(50)
  ]);

  if (e1 || e2) {
    root.innerHTML = `<div class="muted">Erreur: ${(e1||e2).message}</div>`;
    return;
  }

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
        ${(bonus||[]).map(b => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-bonus-id="${b.id}">
            <div style="font-weight:900">${b.title}</div>
            <div class="muted">${b.bookmaker} • ${b.status} • active=${b.active}</div>
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
        ${(books||[]).map(b => `
          <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-book-id="${b.id}">
            <div style="font-weight:900">${b.name}</div>
            <div class="muted">${b.status} • active=${b.active}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

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
      const b = (bonus||[]).find(x => x.id === id);
      if (b) setBonus(b);
    });
  });

  root.querySelectorAll("[data-book-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-book-id");
      const b = (books||[]).find(x => x.id === id);
      if (b) setBook(b);
    });
  });

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
    await renderBonus();
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
    await renderBonus();
  });
}

async function renderInfos() {
  const root = $("tab-infos");
  root.innerHTML = `<div class="muted">Chargement...</div>`;

  const { data, error } = await sb.from("cms_infos").select("*").order("updated_at",{ascending:false}).limit(50);
  if (error) { root.innerHTML = `<div class="muted">Erreur: ${error.message}</div>`; return; }

  root.innerHTML = `
    <div class="card">
      <h3 style="margin:0 0 10px;color:#D4AF37">Infos</h3>
      <label>Titre</label><input id="i_title">
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
      ${(data||[]).map(i => `
        <div class="card" style="border-color:#2a2a2a;cursor:pointer" data-id="${i.id}">
          <div style="font-weight:900">${i.title}</div>
          <div class="muted">${i.status} • active=${i.active}</div>
        </div>
      `).join("")}
    </div>
  `;

  const setForm = (i) => {
    $("i_title").value = i.title || "";
    $("i_content").value = i.content || "";
    $("i_status").value = i.status || "draft";
    $("i_active").value = (i.active !== false) ? "true" : "false";
    $("i_save").dataset.id = i.id;
  };

  root.querySelectorAll("[data-id]").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.getAttribute("data-id");
      const i = data.find(x => x.id === id);
      if (i) setForm(i);
    });
  });

  $("i_save").addEventListener("click", async () => {
    const row = {
      title: $("i_title").value.trim(),
      content: $("i_content").value,
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
    await renderInfos();
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
              <td><button class="btn btn-secondary" data-revoke="${v.user_id}">Désactiver</button></td>
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

  const rows = (data || []).map(r => {
    const meta = r.meta || {};
    const summary =
      r.name === "live_refresh"
        ? `matches=${meta.matches_live ?? 0}, created=${meta.predictions_created ?? 0}, updated=${meta.predictions_updated ?? 0}`
        : `validated=${meta.validated ?? 0}, skipped=${meta.skipped ?? 0}`;

    return `
      <tr>
        <td>${r.name}</td>
        <td>${r.last_run_at ? new Date(r.last_run_at).toLocaleString("fr-FR") : "-"}</td>
        <td>${r.last_ok ? "oui" : "non"}</td>
        <td>
          <div class="muted">${summary}</div>
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

  const modal = document.getElementById("metaModal");
  const pre = document.getElementById("metaContent");
  document.getElementById("closeMeta").onclick = () => (modal.style.display = "none");

  root.querySelectorAll("[data-meta]").forEach(btn => {
    btn.addEventListener("click", () => {
      const meta = JSON.parse(decodeURIComponent(btn.getAttribute("data-meta")));
      pre.textContent = JSON.stringify(meta, null, 2);
      modal.style.display = "block";
    });
  });
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
  alert(`Publié. Articles=${data.counts.articles} / Conseils=${data.counts.conseils} / Bonus=${data.counts.bonus} / Infos=${data.counts.infos} / Bookmakers=${data.counts.bookmakers}`);
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
  await renderBonus();
  await renderInfos();
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

(async () => {
  const session = (await sb.auth.getSession()).data.session;
  if (session) await afterLogin();
})();