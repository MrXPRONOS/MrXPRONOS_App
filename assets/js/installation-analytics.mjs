import { supabaseUrl, supabaseAnonKey } from "./config.js";
import {adminSnapshotLabel} from "./admin-data-freshness.mjs";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const $ = id => document.getElementById(id);
const sb = createClient(supabaseUrl, supabaseAnonKey);
let authenticated = false;
let busy = false;
const count = n => Number(n || 0).toLocaleString("fr-FR");
const label = (id, value) => { $(id).textContent = value; };

function renderTable(id, rows, fields) {
  const target = $(id);
  target.replaceChildren();
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = fields.length;
    td.textContent = "Aucune donnée disponible";
    tr.appendChild(td);
    target.appendChild(tr);
    return;
  }
  rows.forEach(row => {
    const tr = document.createElement("tr");
    fields.forEach(field => {
      const td = document.createElement("td");
      const value = row[field];
      td.textContent = typeof value === "number" ? count(value) : String(value ?? "–");
      tr.appendChild(td);
    });
    target.appendChild(tr);
  });
}

async function isAdmin() {
  const user = await sb.auth.getUser();
  if (!user.data?.user || user.error) return false;
  const { data, error } = await sb.rpc("is_admin");
  return !error && data === true;
}

async function load() {
  if (!authenticated || busy) return;
  busy = true;
  $("refresh").disabled = true;
  label("status", "Actualisation…");
  try {
    const days = Number($("period").value);
    const { data, error } = await sb.rpc("admin_pwa_install_funnel_v2", { p_days: days });
    if (error) throw error;
    const d = data || {}, e = d.events || {};
    ["cta_visible","cta_click","prompt_accepted","appinstalled","standalone_open","guide_open"].forEach((stage, index) => {
      label(["metric-visible","metric-click","metric-accepted","metric-appinstalled","metric-standalone","metric-guide"][index], count(e[stage]));
    });
    renderTable("platforms", Array.isArray(d.platforms) ? d.platforms : [],
      ["platform","cta_visible","cta_click","prompt_accepted","appinstalled","standalone_open"]);
    renderTable("surfaces", Array.isArray(d.surfaces) ? d.surfaces : [],
      ["surface","cta_visible","cta_click","guide_open"]);
    renderTable("daily", Array.isArray(d.daily) ? d.daily : [],
      ["day","visible","clicks","prompt_accepted","appinstalled","standalone_open"]);
    label("status", adminSnapshotLabel("Installations PWA"));
  } catch (error) {
    label("status", "Statistiques indisponibles : " + String(error?.message || error));
  } finally {
    busy = false;
    $("refresh").disabled = false;
  }
}

async function refreshAuth() {
  try { authenticated = await isAdmin(); }
  catch { authenticated = false; }
  $("login-panel").hidden = authenticated;
  $("dashboard").hidden = !authenticated;
  $("logout").hidden = !authenticated;
  label("status", authenticated ? "Accès administrateur confirmé." : "Connexion administrateur requise.");
  if (authenticated) await load();
}

$("login-panel").addEventListener("submit", async event => {
  event.preventDefault();
  const button = $("login-button");
  button.disabled = true;
  label("status", "Connexion…");
  try {
    const { error } = await sb.auth.signInWithPassword({
      email: $("email").value.trim(),
      password: $("password").value
    });
    if (error) throw error;
    await refreshAuth();
    if (!authenticated) {
      await sb.auth.signOut();
      label("status", "Ce compte n'est pas autorisé à consulter les statistiques.");
    }
  } catch (error) {
    label("status", "Connexion refusée : " + String(error?.message || error));
  } finally { button.disabled = false; }
});
$("logout").addEventListener("click", async () => {
  await sb.auth.signOut();
  authenticated = false;
  ["platforms","surfaces","daily"].forEach(id => $(id).replaceChildren());
  await refreshAuth();
});
$("period").addEventListener("change", () => { void load(); });
$("refresh").addEventListener("click", () => { void load(); });
void refreshAuth();
