import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const MISTRAL_API_KEY = Deno.env.get("MISTRAL_API_KEY");
const SUPABASE_URL = Deno.env.get("SUPABASE_URL");
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
const HF_TOKEN = Deno.env.get("HF_TOKEN");
const HF_MODEL = Deno.env.get("HF_MODEL") || "Qwen/Qwen2.5-7B-Instruct";

// Mistral is optional and disabled by default to preserve free-only operation.
if (!SUPABASE_URL) throw new Error("Variable manquante : SUPABASE_URL");
if (!SUPABASE_SERVICE_KEY) throw new Error("Variable manquante : SUPABASE_SERVICE_ROLE_KEY");

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

const BASE_URL = "https://mrxpronos.github.io/MrXPRONOS_App";

const MAIN_PAGES = [
  { name: "Accueil", url: `${BASE_URL}/` },
  { name: "Pronostics", url: `${BASE_URL}/pronos.html` },
  { name: "Historique", url: `${BASE_URL}/historique.html` },
  { name: "Blog", url: `${BASE_URL}/blog.html` },
  { name: "Conseils", url: `${BASE_URL}/conseils.html` },
  { name: "Infos sport", url: `${BASE_URL}/infos.html` },
  { name: "Bonus & Promo", url: `${BASE_URL}/bonus.html` },
  { name: "Contact", url: `${BASE_URL}/contact.html` },
  { name: "Live", url: `${BASE_URL}/live.html` }
];

const OFFICIAL_CONTACTS = {
  whatsapp: "https://wa.me/22899201444",
  telegram: "https://t.me/mr_xpronos"
};

const BUSINESS_CONFIG = {
  promo_code: "XPVIP",
  vip: {
    enabled: false,
    price_fcfa: 0,
    duration_label: "par mois",
    has_24h_offer: false,
    has_free_coupons: true,
    live_url: `${BASE_URL}/live.html`
  },
  support: {
    whatsapp: OFFICIAL_CONTACTS.whatsapp,
    telegram: OFFICIAL_CONTACTS.telegram
  }
};

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const SIMPLE_PATTERNS = [
  /bonjour|salut|hello|coucou/i,
  /merci|thanks|remerci/i,
  /qui es-tu|tu es qui|présente toi/i,
  /comment ça va|ça va bien/i,
  /au revoir|bye|à plus/i,
  /football|match/i
].slice(0, 50);

const FRUSTRATION_KEYWORDS = [
  'mauvais', 'erreur', 'bug', 'pas content', 'frustré', 'déçu',
  'ne marche pas', 'problème', 'aide', 'support',
  'énervé', 'agacé', 'fâché', 'contrarié',
  'perdu', 'confus', 'embêté',
  'insatisfait', 'mécontent',
  'compliqué', 'difficile', 'lent',
  'inutile', 'inefficace',
  'cassé', 'plantage', 'bloqué',
  'faux', 'incorrect', 'erroné',
  'arnaque', 'escroquerie',
  'nul', 'catastrophique'
].slice(0, 50);

const PRONO_KEYWORDS = [
  'pronostic', 'pronos', 'match', 'paris', 'coupon', 'cote',
  'pari', 'parier', 'miser', 'gain', 'score', 'résultat',
  'équipe', 'club', 'statistique', 'analyse', 'bookmaker',
  'double chance'
].slice(0, 50);

const SUPPORT_KEYWORDS = [
  'aide', 'support', 'contact', 'whatsapp', 'telegram',
  'bug', 'problème', 'ne marche pas', 'assistance'
];

const BONUS_KEYWORDS = [
  'bonus', 'promo', 'promotion', 'code', 'xpvip', 'bookmaker',
  '1xbet', '1win', 'betwinner', 'melbet', 'linebet', 'betclic'
];

const LIVE_KEYWORDS = [
  'live', 'direct', 'match en direct',
  'temps réel', 'momentum'
];

const VIP_KEYWORDS = [
  'vip', 'code vip', 'abonnement vip', 'acces vip', 'accès vip'
];

const RESULT_KEYWORDS = [
  'hier', 'résultat', 'résultats', 'validé', 'validés',
  'gagné', 'gagnants', 'perdu', 'échoué'
];

function normalizeQuestion(input: string): string {
  return String(input || "").trim().replace(/\s+/g, " ").toLowerCase();
}

function shortenText(text: string, max = 20000): string {
  const s = String(text || "");
  return s.length > max ? s.slice(0, max) : s;
}

function detectIntent(question: string) {
  const q=normalizeQuestion(question).normalize("NFD").replace(/[\u0300-\u036f]/g,"");
  // Safety has priority over marketing and betting-related keywords.
  if (/\b(1[0-7]\s*ans|mineur|moins de 18|pas majeur|enfant|adolescent)\b/.test(q)) return "underage";
  if (/(\bperdu\b.*\b(argent|fcfa|cfa|euro|paris|mise)\b|me refaire|recuperer mes pertes|dettes de jeu)/.test(q)) return "harm";
  if (/\b(gratuit|gratuite|payer|payant|abonnement|tarif|cout|coute|prix|acces|accessible|sans code|sans abonnement)\b/.test(q) &&
      /\b(vip|live|pronostic|prono|pro)\b/.test(q)) return "access";
  if (/\b(momentum|pression|xg|xa|btts|corners?|plus de 2|over|under|1x2|double chance|handicap|statistiques|en attente|valide)\b/.test(q) &&
      /(que signifie|qu.est.ce|c.est quoi|explique|comment lire|quelle difference|definition|comment interpreter|comprendr|en ewe)/.test(q)) return "knowledge";
  if (/\b(bonus|promo|promotion|xpvip|1xbet|1win|betwinner|melbet|linebet|betclic)\b/.test(q)) return "bonus";
  if (/\b(contact|whatsapp|telegram|telephone|instagram|youtube|facebook|threads|support|aide)\b/.test(q)) return "support";
  if (/\b(live|direct|momentum|pression|signaux)\b/.test(q)) return "live";
  if (/\b(historique|hier|resultats?|valides?|gagnes?|perdu|echoue|roi|semaine|sept derniers jours)\b/.test(q)) return "results";
  if (/\b(pronos?|pronostics?|coupons?|matchs?|rencontres?|demain|ce soir|venir|calendrier|simple|pro)\b/.test(q)) return "prono";
  if (/\b(bonjour|salut|coucou|hello|bonsoir)\b/.test(q)) return "greeting";
  return "generic";
}

function chooseModel(question: string, intent: string): string {
  const q = normalizeQuestion(question);
  const isSimplePattern = SIMPLE_PATTERNS.some(p => p.test(q));
  const isShort = q.length < 60;

  if (intent === "generic" && isSimplePattern && isShort) {
    return "mistral-small-latest";
  }

  return "mistral-large-latest";
}

function buildConversationMessages(
  systemPrompt: string,
  historique: any[] | undefined,
  question: string
) {
  const messages: { role: "system" | "user" | "assistant"; content: string }[] = [
    { role: "system", content: systemPrompt }
  ];

  if (historique && Array.isArray(historique)) {
    for (const msg of historique.slice(-10)) {
      if (!msg || !msg.role || !msg.contenu) continue;

      const role =
        msg.role === "assistant"
          ? "assistant"
          : msg.role === "user"
          ? "user"
          : null;

      if (!role) continue;

      const content = String(msg.contenu).slice(0, 1600).trim();
      if (content) messages.push({ role, content });
    }
  }

  // An older frontend may already have included the current question.
  const last = messages[messages.length - 1];
  if (last?.role === "user" && last.content.trim() === question.trim()) {
    messages.pop();
  }
  messages.push({ role: "user", content: question.slice(0, 1200) });
  return messages;
}

function cleanModelHtmlOutput(html: string): string {
  let cleaned = String(html || "").trim();

  cleaned = cleaned.replace(/^```html\s*/i, "");
  cleaned = cleaned.replace(/^```\s*/i, "");
  cleaned = cleaned.replace(/\s*```$/i, "");
  cleaned = cleaned.replace(/^`+|`+$/g, "").trim();
  cleaned = cleaned.replace(/^<p>\s*```html\s*<\/p>/i, "");
  cleaned = cleaned.replace(/<p>\s*```\s*<\/p>$/i, "");

  // Adoucissement des formulations trop "garanties"
  cleaned = cleaned.replace(/\bgaranti\b/gi, "élevé");
  cleaned = cleaned.replace(/100\s*%\s*(sûr|certain|garanti)/gi, "fort potentiel");
  cleaned = cleaned.replace(/impossible de perdre/gi, "à utiliser avec prudence");
  cleaned = cleaned.replace(/sans risque/gi, "avec prudence");

  return cleaned.trim();
}

// ==== Réponses déterministes (HTML) ====

function renderVipResponse(): string {
  return '<h3>Accès aux pronostics VIP</h3><p>Sur le site officiel Mr XPRONOS, les pronostics Simple, Pro et VIP sont en <strong>accès gratuit</strong>. Le code promo XPVIP est destiné aux offres de partenaires quand il est accepté, et n’est pas un mot de passe pour consulter les pronostics.</p><p><a href="'+BASE_URL+'/pronos.html">Consulter les pronostics</a> · <a href="'+BASE_URL+'/live.html">Ouvrir le LIVE</a></p>';
}
function renderLiveResponse(): string {
  return '<h3>LIVE football</h3><p>La page LIVE de Mr XPRONOS est accessible <strong>gratuitement et directement</strong>, sans abonnement VIP ni code payant.</p><p>Les matchs et statistiques peuvent changer en cours de rencontre. Consulte la page officielle pour les données actualisées.</p><p><a href="'+BASE_URL+'/live.html">Voir les matchs et signaux LIVE</a></p>';
}
function renderSupportResponse(): string {
  return `
    <h3>🛟 Support officiel</h3>
    <p>Pour toute aide ou question sur le service, passe uniquement par nos canaux officiels :</p>
    <ul>
      <li><a href="${BUSINESS_CONFIG.support.whatsapp}" target="_blank">WhatsApp</a></li>
      <li><a href="${BUSINESS_CONFIG.support.telegram}" target="_blank">Telegram</a></li>
    </ul>
    <p><a href="${BASE_URL}/contact.html" target="_blank">Voir la page Contact</a></p>
  `.trim();
}

function renderBonusResponse(bookmakers: any[]): string {
  const items = (bookmakers || []).slice(0, 8).map((b: any) => {
    return `<li><strong>${b.nom}</strong> : ${b.bonus || "Offre disponible selon le bookmaker"}${b.lien_affiliation ? ` — <a href="${b.lien_affiliation}" target="_blank">Accéder au bookmaker</a>` : ""}</li>`;
  }).join("");

  return `
    <h3>🎁 Bonus & code promo</h3>
    <p>Le code promo officiel de Mr XPRONOS est <strong>${BUSINESS_CONFIG.promo_code}</strong>.</p>
    <p>Voici les bookmakers partenaires actuellement disponibles :</p>
    <ul>
      ${items || "<li>Aucun bookmaker partenaire disponible pour le moment.</li>"}
    </ul>
    <p><strong>Important :</strong> vérifie toujours les conditions directement sur la plateforme du bookmaker.</p>
    <p><a href="${BASE_URL}/bonus.html" target="_blank">Voir la page Bonus & Promo</a></p>
  `.trim();
}

function renderGreetingResponse(): string {
  return `
    <p>👋 <strong>Bienvenue sur Mr XPRONOS.</strong></p>
    <p>Je peux t'aider pour :</p>
    <ul>
      <li>Les <a href="${BASE_URL}/pronos.html" target="_blank">pronostics du jour</a></li>
      <li>Les <a href="${BASE_URL}/bonus.html" target="_blank">bonus bookmakers</a></li>
      <li>Le <a href="${BASE_URL}/live.html" target="_blank">PRONO LIVE</a></li>
      <li>Le <a href="${BASE_URL}/contact.html" target="_blank">support</a></li>
    </ul>
  `.trim();
}

function renderPronosticsResponse(pronostics: any[]): string {
  if (!pronostics || pronostics.length === 0) {
    return `
      <p><strong>Aucun pronostic disponible aujourd'hui.</strong></p>
      <p><a href="${BASE_URL}/pronos.html" target="_blank">Voir la page Pronostics</a></p>
    `.trim();
  }

  const rows = pronostics.slice(0, 20).map((p: any) => {
    const match = p.match || `${p.home_team || ""} vs ${p.away_team || ""}`.trim();
    const prediction = p.prediction || p.type || "";
    const cote = p.cote ?? "N/A";
    const score = p.final_score ?? "";
    return `
      <tr>
        <td>${match}</td>
        <td>${prediction}</td>
        <td>${cote}</td>
        <td>${score}</td>
      </tr>
    `.trim();
  }).join("");

  return `
    <h3>⚽ Pronostics du jour</h3>
    <p>Voici une sélection de pronostics du jour. Joue toujours de manière responsable et adapte tes mises.</p>
    <table>
      <thead>
        <tr>
          <th>Match</th>
          <th>Pronostic</th>
          <th>Cote</th>
          <th>Score xPronos</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
    <p><a href="${BASE_URL}/pronos.html" target="_blank">Voir la page Pronostics complète</a></p>
  `.trim();
}

function renderResultatsResponse(resultats: any[]): string {
  if (!resultats || resultats.length === 0) {
    return `
      <p><strong>Aucun résultat disponible pour hier.</strong></p>
      <p><a href="${BASE_URL}/historique.html" target="_blank">Voir l'historique complet</a></p>
    `.trim();
  }

  const rows = resultats.slice(0, 20).map((p: any) => {
    const match = p.match || `${p.home_team || ""} vs ${p.away_team || ""}`.trim();
    const prediction = p.prediction || p.type || "";
    const outcome = p.valide ? "✅ Réussi" : "❌ Échoué";
    const cote = p.cote ?? "N/A";
    return `
      <tr>
        <td>${match}</td>
        <td>${prediction}</td>
        <td>${cote}</td>
        <td>${outcome}</td>
      </tr>
    `.trim();
  }).join("");

  return `
    <h3>📊 Résultats d'hier</h3>
    <p>Voici quelques résultats des pronostics d'hier. Les performances passées ne garantissent pas les résultats futurs.</p>
    <table>
      <thead>
        <tr>
          <th>Match</th>
          <th>Pronostic</th>
          <th>Cote</th>
          <th>Résultat</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
    <p><a href="${BASE_URL}/historique.html" target="_blank">Voir l'historique complet</a></p>
  `.trim();
}

// ==== Accès BDD pronos / résultats / contenu interne ====

async function getPronosticsAvecCache(): Promise<any[]> {
  const now = new Date();
  const { data: cache } = await supabase
    .from('pronostics_cache')
    .select('data, updated_at')
    .eq('id', 1)
    .single();

  let pronostics = null;
  let cacheValide = false;

  if (cache && cache.updated_at) {
    const lastUpdate = new Date(cache.updated_at);
    const diffHeures = (now.getTime() - lastUpdate.getTime()) / (1000 * 60 * 60);
    if (diffHeures < 1) {
      pronostics = cache.data;
      cacheValide = true;
    }
  }

  if (!cacheValide) {
    const today = now.toISOString().split('T')[0];
    let dateCible = today;

    if (now.getHours() >= 22) {
      const demain = new Date(now);
      demain.setDate(demain.getDate() + 1);
      dateCible = demain.toISOString().split('T')[0];
    }

    const { data: fresh, error: fetchError } = await supabase
      .from('pronostics')
      .select('*')
      .eq('date', dateCible);

    if (fetchError) throw fetchError;
    pronostics = fresh || [];

    await supabase
      .from('pronostics_cache')
      .upsert({ id: 1, data: pronostics, updated_at: now.toISOString() });
  }

  return pronostics;
}

async function getResultatsHier(): Promise<any[]> {
  const hier = new Date();
  hier.setDate(hier.getDate() - 1);
  const dateHier = hier.toISOString().split('T')[0];

  const { data, error } = await supabase
    .from('pronostics')
    .select('*')
    .eq('date', dateHier)
    .eq('is_finished', true);

  if (error) throw error;
  return data || [];
}

async function getArticlesSlugs(): Promise<string[]> {
  try {
    const { data, error } = await supabase
      .from('articles')
      .select('slug')
      .limit(20);

    if (error) return [];
    return data?.map((a: any) => a.slug).filter(Boolean) || [];
  } catch {
    return [];
  }
}

async function getConseilsSlugs(): Promise<string[]> {
  try {
    const { data, error } = await supabase
      .from('conseils')
      .select('slug')
      .limit(20);

    if (error) return [];
    return data?.map((c: any) => c.slug).filter(Boolean) || [];
  } catch {
    return [];
  }
}

async function buildInternalLinksText(): Promise<string> {
  const slugs = await getArticlesSlugs();
  const conseilSlugs = await getConseilsSlugs();

  let lines = MAIN_PAGES.map(p => `- ${p.name}: ${p.url}`);

  slugs.slice(0, 10).forEach(slug => {
    lines.push(`- Article: ${BASE_URL}/article.html?slug=${encodeURIComponent(slug)}`);
  });

  conseilSlugs.slice(0, 10).forEach(slug => {
    lines.push(`- Conseil: ${BASE_URL}/conseil.html?slug=${encodeURIComponent(slug)}`);
  });

  return lines.join("\n");
}

// ==== Cache assistant ====

async function getAssistantCache(normalizedQuestion: string): Promise<string | null> {
  try {
    const { data, error } = await supabase
      .from("assistant_cache")
      .select("answer, expires_at")
      .eq("normalized_question", normalizedQuestion)
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error || !data) return null;

    if (data.expires_at && new Date(data.expires_at).getTime() < Date.now()) {
      return null;
    }

    return data.answer || null;
  } catch {
    return null;
  }
}

async function saveAssistantCache(normalizedQuestion: string, question: string, answer: string) {
  try {
    const expiresAt = new Date(Date.now() + 12 * 60 * 60 * 1000).toISOString();

    await supabase.from("assistant_cache").insert({
      normalized_question: normalizedQuestion,
      question,
      answer: shortenText(answer, 20000),
      created_at: new Date().toISOString(),
      expires_at: expiresAt
    });
  } catch {
    // ignore
  }
}

const FONCTIONNALITES = `
1. Pronostics quotidiens : Simple, Pro, VIP.
2. Analyses avancées : H2H, forme récente, score xPronos.
3. PRONO LIVE : statistiques et signaux en direct.
4. Consultation gratuite des catégories Simple, Pro et VIP.
5. Assistant IA intégré.
6. Bonus bookmakers avec code XPVIP.
7. Historique et taux de réussite.
8. Blog, conseils, actualités football.
9. Installation mobile (PWA).
10. Support via WhatsApp et Telegram.
`;

// ==== Prompt système LLM (assistant général, contraintes fortes) ====

function buildSystemPrompt(params: {
  intent: string;
  bookmakersText: string;
  contactsText: string;
  internalLinksText: string;
  pronosticsText: string;
  resultatsText: string;
  isFrustrated: boolean;
  hasPronos: boolean;
}) {
  const {
    intent,
    bookmakersText,
    contactsText,
    internalLinksText,
    pronosticsText,
    resultatsText,
    isFrustrated,
    hasPronos
  } = params;

  let prompt = `
Tu es "Mr XPRONOS", assistant IA expert en paris sportifs. Tu reponds en francais dans un ton amical et direct, comme un parieur experimente qui explique aux autres.

Regles absolues :
1. Reponds en HTML pur uniquement : <p>, <h3>, <ul>, <li>, <a>, <table>, <thead>, <tbody>, <tr>, <th>, <td>, <strong>.
2. N'utilise jamais de markdown.
3. Ne commence jamais la reponse par \`\`\`html, \`\`\` ou des backticks.
4. Ne termine jamais la reponse par \`\`\` ou des backticks.
5. Retourne directement le HTML brut, sans balise de code.
6. N'invente jamais un prix, une duree, une offre speciale ou un avantage commercial.
7. Si une information commerciale n'est pas explicitement fournie, dis a l'utilisateur de contacter le support officiel.
8. N'utilise que les contacts officiels fournis ci-dessous.
9. N'utilise que les bookmakers fournis ci-dessous.
10. N'utilise que les liens (internes ou bookmakers) explicitement fournis ci-dessous. Tu ne crees pas de nouveaux liens externes, meme si tu connais le site du bookmaker.
11. Tous les montants doivent etre exprimes en Francs CFA (F CFA).
12. Reponse claire, utile, concise, professionnelle mais chaleureuse.
13. Mets les points importants en <strong>.
14. Tu ne crees JAMAIS de nouveaux coupons ou pronostics : pas de liste de matchs inventes, pas de "Equipe A vs Equipe B : 1X" invente. Si tu parles de pronostics, tu restes general et tu renvoies vers la page Pronostics.
15. Tu ne modifies pas les pronostics officiels : ils sont geres par le site et l'application, pas par toi.
16. Tu ne promets jamais "garanti", "certain", "100% sur", "impossible de perdre", "sans risque". Rappelle que les paris comportent toujours un risque.

Comportement :
- Tu peux expliquer des notions (paris simples, combines, value bet, bankroll, tilt, erreurs a eviter).
- Tu peux donner des exemples abstraits (Equipe A / Equipe B) mais ce ne sont PAS des pronostics officiels.
- Tu poses au maximum 1 question de relance, et seulement si c'est naturel.
- Tu evites de repeter mot pour mot toujours la meme phrase.

${isFrustrated ? `
L'utilisateur semble frustre ou en difficulte : sois empathique, rassurant, et n'hesite pas a proposer un contact humain (WhatsApp / Telegram).` : ""}

Contexte :
- Bookmakers autorises :
${bookmakersText || "Aucun bookmaker partenaire n'est defini."}

- Contacts officiels :
${contactsText}

- Liens internes utiles :
${internalLinksText}

- Fonctionnalites de Mr XPRONOS :
${FONCTIONNALITES}
`;

  if (intent === "generic" || intent === "prono") {
    // On donne une vision generale, sans liste detaillee a manipuler
    prompt += `
- Informations sur les pronostics :
${hasPronos ? `Il y a des pronostics disponibles sur la page Pronostics : ${BASE_URL}/pronos.html` : "Aucun pronostic n'est disponible pour le moment."}
`;
  }

  if (intent === "results") {
    prompt += `
- Informations generales sur les resultats recents :
${resultatsText || "Aucun resume de resultat n'est disponible."}
`;
  }

  prompt += `
Intention principale detectee pour ce message : "${intent}". Adapte ta reponse a ce contexte, mais respecte toujours les regles ci-dessus.
  `;

  return prompt.trim();
}

function buildPronosticsText(pronostics: any[]): string {
  if (!pronostics || pronostics.length === 0) return "Aucun pronostic aujourd'hui.";
  // On ne fournit plus la liste detaillee au LLM, juste une info globale
  return `Il y a actuellement ${pronostics.length} pronostics disponibles sur la page Pronostics : ${BASE_URL}/pronos.html`;
}

function buildResultatsText(resultats: any[]): string {
  if (!resultats || resultats.length === 0) return "Aucun resultat hier.";
  const gagne = resultats.filter((p: any) => p.valide).length;
  const total = resultats.length;
  return `Hier, ${gagne} pronostics sur ${total} ont ete valides. Les performances passees ne garantissent pas les resultats futurs.`;
}

// ==== Embeddings / FAQ ====

async function getEmbedding(text: string): Promise<number[]> {
  const response = await fetch("https://api.mistral.ai/v1/embeddings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${MISTRAL_API_KEY}`,
    },
    body: JSON.stringify({
      model: "mistral-embed",
      input: text,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Mistral embeddings error (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  return data.data[0].embedding;
}

async function findSimilarFAQ(embedding: number[]) {
  try {
    const { data: official, error: err1 } = await supabase.rpc("match_faq_official", {
      query_embedding: embedding,
      match_threshold: 0.6,
    });

    if (!err1 && official && official.length > 0) {
      return official[0];
    }
  } catch {
    // ignore
  }

  try {
    const { data, error } = await supabase.rpc("match_faq", {
      query_embedding: embedding,
      match_threshold: 0.75,
    });

    if (error) return null;
    return data?.[0] || null;
  } catch {
    return null;
  }
}

// ==== Appels LLM (HF + Mistral) ====

async function callHuggingFace(
  messages: { role: "system" | "user" | "assistant"; content: string }[],
  model: string
): Promise<string> {
  if (!HF_TOKEN) {
    throw new Error("HF_TOKEN manquant");
  }

  const response = await fetch("https://router.huggingface.co/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${HF_TOKEN}`,
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.5,
      max_tokens: 1200
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`HF router error (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  const content = data?.choices?.[0]?.message?.content;

  if (!content) {
    throw new Error("Réponse Hugging Face invalide");
  }

  return String(content).trim();
}

async function callMistral(
  messages: { role: "system" | "user" | "assistant"; content: string }[],
  model: string
): Promise<string> {
  const response = await fetch("https://api.mistral.ai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${MISTRAL_API_KEY}`,
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.5,
      max_tokens: 3000,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Mistral chat error (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  return data.choices[0].message.content;
}

async function callGroq(
  messages: { role: "system" | "user" | "assistant"; content: string }[]
): Promise<string> {
  const token=Deno.env.get("GROQ_API_KEY");
  if (!token) throw new Error("GROQ_API_KEY absent");
  const response=await fetch("https://api.groq.com/openai/v1/chat/completions",{
    method:"POST",
    headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`},
    body:JSON.stringify({
      model:Deno.env.get("GROQ_MODEL") || "openai/gpt-oss-20b",
      messages,temperature:0.3,max_tokens:850
    })
  });
  if(!response.ok) throw new Error("Groq unavailable: HTTP "+response.status);
  const data=await response.json();
  const content=data?.choices?.[0]?.message?.content;
  if(typeof content!=="string" || !content.trim()) throw new Error("Groq empty reply");
  return content.trim();
}
async function callPrimaryModel(
  messages: { role: "system" | "user" | "assistant"; content: string }[],
  mistralModel: string,
  _intent: string
): Promise<string> {
  // 1. Groq free tier (if key configured); 2. HF free credits;
  // 3. Mistral only by explicit opt-in, never silently spend money.
  if (Deno.env.get("GROQ_API_KEY")) {
    try {return await callGroq(messages);} catch(err){console.warn("Groq unavailable",String(err));}
  }
  if(HF_TOKEN){
    try {return await callHuggingFace(messages,HF_MODEL);} catch(err){console.warn("HF unavailable",String(err));}
  }
  if(Deno.env.get("ALLOW_MISTRAL_FALLBACK")==="true" && MISTRAL_API_KEY) {
    return await callMistral(messages,mistralModel);
  }
  throw new Error("Free LLM providers unavailable; paid fallback disabled");
}

function buildSafeFallbackAnswer(intent: string): string {
  if (intent === "support" || intent === "vip" || intent === "live") {
    return renderSupportResponse();
  }

  if (intent === "bonus") {
    return `
      <p><strong>Impossible de récupérer les informations bonus pour le moment.</strong></p>
      <p>Tu peux consulter directement la page suivante :</p>
      <p><a href="${BASE_URL}/bonus.html" target="_blank">Bonus & Promo</a></p>
    `;
  }

  if (intent === "prono") {
    return `
      <p><strong>Impossible de générer la réponse pour le moment.</strong></p>
      <p>Tu peux consulter directement la page des pronostics :</p>
      <p><a href="${BASE_URL}/pronos.html" target="_blank">Voir les pronostics</a></p>
    `;
  }

  return '<p>Je n’ai pas assez d’informations fiables pour répondre précisément. Peux-tu reformuler ou préciser le sujet ? Je peux aider pour le football, les pronostics, les statistiques, le LIVE et le support.</p><p><a href="'+BASE_URL+'/contact.html">Contacter le support</a></p>';}


// Sources publiques déjà utilisées par les pages du site; jamais d'invention de résultat.
const safeHtml=(value: unknown)=>String(value??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
async function publishedJson(file: string): Promise<any | null> {
  try {
    const response=await fetch(BASE_URL+"/"+file,{signal:AbortSignal.timeout(5500),headers:{"Accept":"application/json"}});
    if(!response.ok) return null;
    return await response.json();
  }catch{return null;}
}
const publicLink=(file: string,label: string)=>'<a href="'+BASE_URL+'/'+file+'">'+label+'</a>';
function sourceNote(source: any): string {
  const ts=source?.generated_at?new Date(source.generated_at).toISOString().replace("T"," ").slice(0,16)+" UTC":"date inconnue";
  return '<p><small>Source : données publiées sur le site, mise à jour '+safeHtml(ts)+'. Les informations peuvent évoluer.</small></p>';
}
async function answerPublishedMatches(question: string): Promise<string> {
  const feed=await publishedJson("data.json");
  const link='<p>'+publicLink("pronos.html","Consulter tous les pronostics")+' · '+publicLink("live.html","Matchs LIVE")+'</p>';
  if(!feed||!Array.isArray(feed.matches)) return '<p>Je ne peux pas vérifier la liste actuelle des matchs. Consulte les pages du site directement.</p>'+link;
  const q=normalizeQuestion(question);
  const shift=/demain/.test(q)?1:0;
  const d=new Date(Date.now()+shift*86400000).toISOString().slice(0,10);
  let matches=feed.matches.filter((x:any)=>String(x.date||x.event_date||"").slice(0,10)===d);
  if(/\bsimple\b/.test(q))matches=matches.filter((m:any)=>String(m.category||m.source_category||"").toLowerCase().includes("simple"));
  if(/\bpro\b/.test(q))matches=matches.filter((m:any)=>String(m.category||m.source_category||"").toLowerCase().includes("pro"));
  if(/\bvip\b/.test(q))matches=matches.filter((m:any)=>String(m.category||m.source_category||"").toLowerCase().includes("vip"));
  const label=shift?"demain":"aujourd'hui";
  if(matches.length===0)return '<p>Je ne trouve aucune entrée publiée pour '+label+' ('+d+') avec ces critères. Cela ne veut pas dire qu’aucun match n’a lieu.</p>'+link+sourceNote(feed);
  let answer='<p><strong>'+matches.length+' entrée(s) publiée(s)</strong> pour '+label+' ('+d+'). Voici quelques matchs figurant dans les données du site :</p><ul>';
  answer+=matches.slice(0,8).map((m:any)=>{
    const home=safeHtml(m.home_team||m.home||"Équipe domicile");
    const away=safeHtml(m.away_team||m.away||"Équipe extérieur");
    const cat=safeHtml(m.category||m.source_category||"");
    return '<li>'+home+' – '+away+(cat?' ('+cat+')':'')+'</li>';
  }).join("");
  return answer+'</ul><p>Ce sont des entrées publiées, pas une garantie de sélection encore active ni de victoire.</p>'+link+sourceNote(feed);
}
async function answerPublishedHistory(question: string): Promise<string> {
  const feed=await publishedJson("data.json");
  const link='<p>'+publicLink("historique.html","Voir les résultats et leur validation sur la page Historique")+'</p>';
  if(!feed||!Array.isArray(feed.matches)) return '<p>Je ne peux pas vérifier les résultats publiés actuellement.</p>'+link;
  const q=normalizeQuestion(question);
  const end=new Date();
  const from=new Date(end.getTime()-(/\bsemaine\b|7\s*jours|sept derniers jours/.test(q)?7:1)*86400000).toISOString().slice(0,10);
  const to=(/\bsemaine\b|7\s*jours|sept derniers jours/.test(q)?end:new Date(end.getTime()-86400000)).toISOString().slice(0,10);
  const entries=feed.matches.filter((m:any)=>{const d=String(m.date||m.event_date||"").slice(0,10);return d>=from&&d<=to;});
  if(!entries.length)return '<p>Aucune entrée retrouvée dans les données publiées entre le '+from+' et le '+to+'. Je ne peux pas conclure qu’aucun résultat n’existe sans la vérification de la page Historique.</p>'+link;
  return '<p><strong>'+entries.length+' entrée(s) historique(s)</strong> sont présentes pour la période du '+from+' au '+to+'. Je ne peux pas déduire le nombre de paris gagnés ou le ROI à partir de ce seul décompte : ces valeurs nécessitent les statuts de validation officiels.</p>'+link+sourceNote(feed);
}
async function answerPublishedBonus(question: string): Promise<string> {
  const offers=await publishedJson("bonus.json");
  const q=normalizeQuestion(question);
  const link='<p>'+publicLink("bonus.html","Voir toutes les offres et leurs conditions")+'</p>';
  const base='<p>Le code promo du site est <strong>XPVIP</strong>, uniquement lorsqu’il est accepté par le partenaire. Une offre publiée n’est pas une confirmation de son éligibilité actuelle.</p>';
  if(!Array.isArray(offers))return base+'<p>La liste des offres n’est pas accessible pour vérification.</p>'+link;
  const bk=["1xbet","1win","betwinner","melbet","linebet","betclic"].find(x=>q.replace(/\s+/g,"").includes(x));
  const active=offers.filter((x:any)=>x.active!==false&&(!bk||String(x.bookmaker||"").toLowerCase().replace(/\s+/g,"").includes(bk)));
  const items=active.slice(0,6).map((x:any)=>'<li><strong>'+safeHtml(x.bookmaker||"Partenaire")+' : '+safeHtml(x.title||"Offre")+'</strong> — '+safeHtml(x.description||"Conditions à vérifier")+'</li>').join("");
  return base+(items?'<p>Exemples présents sur la page Bonus :</p><ul>'+items+'</ul>':'<p>Aucune offre trouvée avec ce filtre.</p>')+link;
}
async function answerOfficialFAQ(question: string): Promise<string | null> {
  const q=normalizeQuestion(question).normalize("NFD").replace(/[\u0300-\u036f]/g,"");
  const {data}=await supabase.from("faq").select("question,reponse").eq("official",true).limit(100);
  const rows=data||[];
  const canonical=(s:string)=>normalizeQuestion(s).normalize("NFD").replace(/[\u0300-\u036f]/g,"")
     .replace(/^(qu.est.ce que|que signifie|c.est quoi|definition de|comment lire|quelle est la difference entre)\s*/,"")
     .replace(/[^a-z0-9]+/g," ").trim();
  const target=canonical(q);
  const exact=rows.find((x:any)=>canonical(x.question)===target);
  if(exact) return exact.reponse;
  // Match only a clearly identified technical term; never match on boilerplate.
  const concepts=["xg","xa","1x2","btts","dnb","corners","corner","double chance","handicap asiatique","over et under"];
  const matched=concepts.filter(t=>new RegExp("(^|[^a-z0-9])"+t.replace(/ /g,"\\s+")+"([^a-z0-9]|$)").test(" "+target+" "));
  if(matched.length!==1)return null;
  const concept=matched[0];
  const row=rows.find((x:any)=>canonical(x.question)===concept || canonical(x.question)===("un "+concept));
  return row?.reponse||null;
}

// ==== HTTP handler ====

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const url = new URL(req.url);

  if (req.method === "GET" && url.pathname.endsWith("/suggestions")) {
    return new Response(JSON.stringify({ suggestions: [] }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed. Use POST." }), {
      status: 405,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  if (body.action === "feedback") {
    const { user_id, conversation_id, question, reponse, feedback } = body;
    if (typeof feedback !== "boolean") return new Response(JSON.stringify({error:"invalid feedback"}), {status:400,headers:{...corsHeaders,"Content-Type":"application/json"}});
    const matched = conversation_id && user_id ? await supabase.from("conversations").select("id,question,reponse").eq("id",conversation_id).eq("user_id",user_id).maybeSingle() : {data:null};
    const item = {user_id,conversation_id:matched.data?.id ?? null,
       question:matched.data?.question ?? String(question || "").slice(0,1200),
       reponse:matched.data?.reponse ?? String(reponse || "").slice(0,8000),feedback};
    const {error: insertError} = await supabase.from("feedback").insert(item);
    if (insertError) return new Response(JSON.stringify({error:"cannot save feedback"}),{status:500,headers:{...corsHeaders,"Content-Type":"application/json"}});
    return new Response(JSON.stringify({ success: true }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const { question, user_id } = body;
  const historique = Array.isArray(body.historique) ? body.historique.slice(-8) : [];
  const page_context = typeof body.page_context?.pathname === "string"
    ? body.page_context.pathname.slice(0, 120) : "";

  if (typeof question !== "string" || !question.trim() || question.length > 1200) {
    return new Response(JSON.stringify({ error: "Question invalide ou trop longue" }), {
      status: 400,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  // Page context is restricted to a pathname; never treat it as a source of verified match data.
  void page_context;
  // Budget guard: IP-based quota, not a client-supplied user_id.
  const rawIP = req.headers.get("cf-connecting-ip") || req.headers.get("x-real-ip") || "unknown";
  const ipHash = await crypto.subtle.digest("SHA-256",new TextEncoder().encode("assistant:"+rawIP.slice(0,120)));
  const key = "assistant_"+Array.from(new Uint8Array(ipHash)).map(x=>x.toString(16).padStart(2,"0")).join("");
  const { data: allowed, error: limitError } = await supabase.rpc("assistant_take_rate_slot", {
    p_key: key, p_limit: 20, p_window_seconds: 900
  });
  if (limitError || allowed !== true) {
    return new Response(JSON.stringify({error:"Limite temporaire atteinte. Réessaie plus tard."}),{
      status:429,headers:{...corsHeaders,"Content-Type":"application/json","Retry-After":"300"}
    });
  }
  const normalizedQuestion = normalizeQuestion(question);
  const intent = detectIntent(normalizedQuestion);
  const isFrustrated = FRUSTRATION_KEYWORDS.some(kw => normalizedQuestion.includes(kw));

  try {
    const answerNow=async(answer: string, source="site")=>{
      const {data: conversation}=await supabase.from("conversations")
        .insert({user_id,question,reponse:shortenText(answer,20000),from_cache:source==="faq"})
        .select("id").maybeSingle();
      return new Response(JSON.stringify({answer,source,from_cache:source==="faq",conversation_id:conversation?.id??null}),{
        headers:{...corsHeaders,"Content-Type":"application/json"}
      });
    };
    if(intent==="underage")return await answerNow(
      '<p>Les paris sportifs sont réservés aux adultes. Si tu as moins de 18 ans, ne mise pas d’argent. Tu peux consulter les actualités football sans parier.</p>',"safety");
    if(intent==="harm")return await answerNow(
      '<p>Ne cherche pas à récupérer des pertes en augmentant les mises. Arrête les paris pour le moment, protège ton budget et demande du soutien à une personne de confiance si tu en ressens le besoin.</p>',"safety");
    if(intent==="access")return await answerNow(
      '<p>Sur le site Mr XPRONOS, les catégories <strong>Simple, Pro, VIP et le LIVE sont consultables gratuitement</strong>. Aucun abonnement VIP payant ni code n’est exigé pour ces pages. Le code <strong>XPVIP</strong> concerne les offres de partenaires lorsqu’il est accepté.</p><p>'+
      publicLink("pronos.html","Pronostics")+' · '+publicLink("live.html","LIVE")+'</p>',"site");
    if(intent==="greeting")return await answerNow(renderGreetingResponse(),"site");
    if(intent==="bonus")return await answerNow(await answerPublishedBonus(question),"bonus.json");
    if(intent==="support"){
      const ans='<p>Tu peux joindre le support via <a href="'+OFFICIAL_CONTACTS.whatsapp+'">WhatsApp</a>, <a href="'+OFFICIAL_CONTACTS.telegram+'">Telegram</a> ou par téléphone au <a href="tel:+22899201444">+228 99 20 14 44</a>.</p>'+
         '<p>Réseaux officiels : <a href="https://www.instagram.com/mr_xpronos">Instagram</a> · <a href="https://youtube.com/@mrxpronos">YouTube</a> · <a href="https://www.facebook.com/share/1DsG6H6gf1/">Facebook</a> · <a href="https://www.threads.com/@mr_xpronos">Threads</a>.</p>'+
         '<p>'+publicLink("contact.html","Page Contact")+'</p>';
      return await answerNow(ans,"contact");
    }
    if(intent==="live"){
      const q=normalizeQuestion(question);
      if(/ne s.affichent pas|n.apparaissent pas|aucun signal|signaux ne|bug|erreur/.test(q))
        return await answerNow('<p>Un signal peut ne pas apparaître si aucun match ne répond aux critères, si les données ont du retard ou si un filtre masque les résultats. Recharge la page, vérifie la connexion et les filtres; contacte le support si cela continue.</p><p>'+publicLink("live.html","Vérifier la page LIVE")+'</p>',"site");
      if(/actualis|rafraich|mettre a jour/.test(q))
        return await answerNow('<p>Sur le LIVE, recharge la page ou utilise le contrôle d’actualisation disponible. Vérifie toujours la date et la minute des données affichées.</p><p>'+publicLink("live.html","Ouvrir le LIVE")+'</p>',"site");
      if(/score live|score en direct/.test(q))
        return await answerNow('<p>Je ne peux pas confirmer ici le score d’une équipe en temps réel. Consulte les informations directement sur '+publicLink("live.html","la page LIVE")+'.</p>',"site");
      if(/momentum|pression/.test(q))
        return await answerNow('<p>Le momentum décrit la dynamique récente du match; la pression offensive est un indicateur construit à partir des actions dangereuses. Aucun des deux ne garantit un but.</p><p>'+publicLink("live.html","Voir les statistiques LIVE")+'</p>',"guide");
      return await answerNow(renderLiveResponse(),"site");
    }
    if(intent==="prono"){
      if(/garanti|100\s*%|certain|sans risque|matchs?\s+s[uû]rs?/i.test(question))
        return await answerNow('<p>Aucun pronostic n’est garanti, même avec de bonnes statistiques. '+publicLink("pronos.html","Consulter les pronostics officiels")+' et leurs dates de mise à jour.</p>',"safety");
      return await answerNow(await answerPublishedMatches(question),"data.json");
    }
    if(intent==="results"){
      if(/garanti|garantissent|sans risque/i.test(question))
        return await answerNow('<p>Non. Les résultats passés ne garantissent jamais des résultats futurs. Ils servent à décrire les performances, pas à certifier un gain.</p>',"guide");
      if(/ou est|où est|ou voir|où voir|comment consulter|ou trouver/i.test(normalizeQuestion(question)))
        return await answerNow('<p>Tu peux retrouver les résultats précédents sur '+publicLink("historique.html","la page Historique")+'.</p>',"site");
      return await answerNow(await answerPublishedHistory(question),"data.json");
    }
    if(intent==="knowledge"){
      const q=normalizeQuestion(question);
      if(/xg/i.test(q)&&/1x2/i.test(q))
        return await answerNow('<p><strong>xG</strong> mesure statistiquement la qualité des occasions de tir. <strong>1X2</strong> est un marché à trois issues : victoire à domicile (1), nul (X), victoire à l’extérieur (2). Ce ne sont pas deux mesures comparables.</p>',"guide");
      if(/en attente/i.test(q))
        return await answerNow('<p>Un pronostic <strong>en attente</strong> n’est pas encore validé comme gagné ou perdu. Il ne doit pas entrer dans le calcul des taux de réussite avant une vérification.</p>',"guide");
      if(/valid[eé]|validation/i.test(q))
        return await answerNow('<p>La validation d’un pronostic consiste à vérifier son issue après l’événement. Vérifie le statut exact sur '+publicLink("historique.html","la page Historique")+' : réussi, échoué ou en attente.</p>',"guide");
      if(/momentum|pression/i.test(q))
        return await answerNow('<p>Le momentum désigne la dynamique du jeu; la pression offensive dépend de la définition du fournisseur des statistiques. Aucun indicateur n’est une garantie de but.</p>',"guide");
      const exactFAQ=await answerOfficialFAQ(question);
      if(exactFAQ)return await answerNow(exactFAQ,"faq");
      if(/corners?/i.test(q))return await answerNow('<p>Un corner est un coup de pied de coin accordé quand le ballon franchit la ligne de but après avoir été touché en dernier par un défenseur, sans but marqué.</p>',"guide");
      if(/over|plus de 2/i.test(q))
        return await answerNow('<p>« Plus de 2,5 buts » signifie au moins trois buts au total dans le match. Vérifie toujours la période comptée par l’opérateur.</p>',"guide");
      return await answerNow('<p>Peux-tu préciser le terme football ? Je peux expliquer xG, xA, BTTS, 1X2, corners, handicaps et autres marchés.</p>',"guide");
    }
    if(intent==="generic"){
      const q=normalizeQuestion(question);
      if(/articles|actualites|blog|conseils|bankroll/.test(q)){
        const isAdvice=/conseil|bankroll/.test(q);
        const file=isAdvice?"conseils.json":"articles.json";
        const items=await publishedJson(file);
        const link=publicLink(isAdvice?"conseils.html":"blog.html",isAdvice?"Tous les conseils":"Tous les articles");
        const recent=Array.isArray(items)?items.filter((x:any)=>x.active!==false).slice(0,5):[];
        return await answerNow('<p>Voici des contenus publiés sur le site :</p><ul>'+
          recent.map((x:any)=>'<li>'+safeHtml(x.title||"Article")+'</li>').join("")+
          '</ul><p>'+link+'</p>',file);
      }
      const found=await answerOfficialFAQ(question);
      if(found)return await answerNow(found,"faq");
    }
    // Other questions fall through to existing optional free AI and its safe fallback.
    // Bookmakers actifs
    const { data: bookmakersData } = await supabase
      .from("bookmakers")
      .select("nom, lien_affiliation, bonus, description")
      .eq("active", true)
      .order("nom", { ascending: true });

    const bookmakers = [...(bookmakersData || [])].sort((a, b) =>
      a.nom === "1xBet" ? -1 : b.nom === "1xBet" ? 1 : 0
    );

    // Réponses déterministes (pas de LLM)
    if (intent === "vip") {
      const answer = renderVipResponse();
      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: answer,
        from_cache: false,
      });

      return new Response(JSON.stringify({ answer, from_cache: false }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (intent === "live") {
      const answer = renderLiveResponse();
      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: answer,
        from_cache: false,
      });

      return new Response(JSON.stringify({ answer, from_cache: false }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (intent === "support") {
      const answer = renderSupportResponse();
      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: answer,
        from_cache: false,
      });

      return new Response(JSON.stringify({ answer, from_cache: false }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (intent === "bonus") {
      const answer = renderBonusResponse(bookmakers);
      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: answer,
        from_cache: false,
      });

      return new Response(JSON.stringify({ answer, from_cache: false }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (/^bonjour$|^salut$|^hello$|^coucou$/.test(normalizedQuestion)) {
      const answer = renderGreetingResponse();
      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: answer,
        from_cache: false,
      });

      return new Response(JSON.stringify({ answer, from_cache: false }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Cache LLM (uniquement pour les réponses générées)
    const cachedAnswer = await getAssistantCache(normalizedQuestion);
    if (cachedAnswer && intent === "generic" && (!historique || historique.length === 0) && !/aujourd|demain|hier|live|prix|tarif/i.test(question)) {
      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: shortenText(cachedAnswer, 20000),
        from_cache: true,
      });

      return new Response(JSON.stringify({ answer: cachedAnswer, from_cache: true }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // First try the official FAQ without a paid embeddings API.
    if (intent === "generic" && (!historique || historique.length <= 2)) {
      const {data:approvedFAQ} = await supabase.from("faq").select("question,reponse").eq("official",true).limit(100);
      const tokens = (v:string) => new Set(String(v||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().split(/[^a-z0-9]+/).filter(w=>w.length>3 && w!=="comment"));
      const qTokens=tokens(question);
      let choice:any=null,score=0;
      for(const entry of approvedFAQ||[]) {
        const t=tokens(entry.question);
        const intersection=[...qTokens].filter(w=>t.has(w)).length;
        const value=intersection/Math.max(qTokens.size,t.size,1);
        if(value>score){choice=entry;score=value;}
      }
      if(choice && score>=0.70) {
        await supabase.from("conversations").insert({user_id,question,reponse:choice.reponse,from_cache:true});
        return new Response(JSON.stringify({answer:choice.reponse,from_cache:true,source:"faq"}),{headers:{...corsHeaders,"Content-Type":"application/json"}});
      }
    }
    // Embeddings / FAQ : seulement pour les questions GENERIQUES (pour ne pas bloquer PRONO / RESULT)
    let embedding: number[] | null = null;
    let similar = null;

    // Zero verified FAQ = no embeddings request, therefore no unnecessary paid call.
    const { count: faqCount } = await supabase.from("faq")
      .select("id", { count:"exact", head:true }).eq("official",true);
    if (false && (faqCount || 0) > 0 && (!historique || historique.length <= 2) && intent === "generic") {
      try {
        embedding = await getEmbedding(question);
        similar = await findSimilarFAQ(embedding);
      } catch {
        similar = null;
      }
    }

    if (similar && intent === "generic") {
      const faqAnswer = cleanModelHtmlOutput(similar.reponse || "");

      try {
        await supabase
          .from("faq")
          .update({ usage_count: (similar.usage_count || 0) + 1 })
          .eq("id", similar.id);
      } catch {
        // ignore
      }

      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: shortenText(faqAnswer, 20000),
        from_cache: true,
      });

      return new Response(JSON.stringify({ answer: faqAnswer, from_cache: true }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Pronostics du jour
    const pronostics = await getPronosticsAvecCache();
    const hasPronos = pronostics && pronostics.length > 0;

    // Résultats hier (pour l'intent results)
    let resultatsHier: any[] = [];
    if (intent === "results") {
      resultatsHier = await getResultatsHier();
    }

    // Intent PRONO : réponse déterministe, sans LLM => pas de coupons inventés
    if (intent === "prono") {
      if (!hasPronos) {
        const now = new Date();
        let message = "Aucun pronostic disponible aujourd'hui.";
        if (now.getHours() >= 22) {
          message = "Aucun pronostic disponible pour demain pour le moment. Reviens plus tard ou consulte la page Pronostics.";
        }

        const answer = `<p>${message}</p><p><a href="${BASE_URL}/pronos.html" target="_blank">Voir la page Pronostics</a></p>`;

        await supabase.from("conversations").insert({
          user_id,
          question,
          reponse: answer,
          from_cache: false,
        });

        return new Response(JSON.stringify({
          answer,
          from_cache: false
        }), {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }

      const answer = renderPronosticsResponse(pronostics);
      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: answer,
        from_cache: false,
      });

      return new Response(JSON.stringify({ answer, from_cache: false }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Intent RESULTS : réponse déterministe (table de résultats)
    if (intent === "results") {
      const answer = renderResultatsResponse(resultatsHier);
      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: answer,
        from_cache: false,
      });

      return new Response(JSON.stringify({ answer, from_cache: false }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Contexte pour le LLM (assistant général : explications, pédagogie, discussion)
    const internalLinksText = await buildInternalLinksText();

    const bookmakersText = bookmakers.map(b =>
      `- ${b.nom} : ${b.bonus} | lien: ${b.lien_affiliation}`
    ).join("\n");

    const contactsText = `
- WhatsApp : ${OFFICIAL_CONTACTS.whatsapp}
- Telegram : ${OFFICIAL_CONTACTS.telegram}
`.trim();

    const pronosticsText = buildPronosticsText(pronostics || []);
    const resultatsText = buildResultatsText(resultatsHier || []);

    const systemPrompt = buildSystemPrompt({
      intent,
      bookmakersText,
      contactsText,
      internalLinksText,
      pronosticsText,
      resultatsText,
      isFrustrated,
      hasPronos
    }) + (page_context === "/live.html"
      ? "\nContexte de navigation : l'utilisateur consulte le LIVE. Les informations de match doivent venir exclusivement des données fournies dans le prompt, jamais du chemin de page."
      : page_context === "/historique.html"
      ? "\nContexte de navigation : l'utilisateur consulte l'Historique. Ne pas inventer les résultats ou leur validation."
      : page_context === "/pronos.html"
      ? "\nContexte de navigation : l'utilisateur consulte la page Pronostics. Ne pas inventer de coupons."
      : "");

    const messages = buildConversationMessages(systemPrompt, historique, question);
    const model = chooseModel(question, intent);

    const rawAnswer = await callPrimaryModel(messages, model, intent);
    const cleanedAnswer = cleanModelHtmlOutput(rawAnswer);
    const safeAnswer = shortenText(cleanedAnswer, 20000);

    if (intent === "generic" && (!historique || historique.length === 0) && !/aujourd|demain|hier|live|prix|tarif/i.test(question)) {
      await saveAssistantCache(normalizedQuestion, question, safeAnswer);
    }

    const { data: conv } = await supabase.from("conversations").insert({
      user_id,
      question,
      reponse: safeAnswer,
      from_cache: false,
    }).select("id").single();

    return new Response(JSON.stringify({
      answer: safeAnswer,
      from_cache: false,
      conversation_id: conv?.id ?? null
    }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Erreur assistant:", error);

    const fallbackAnswer = buildSafeFallbackAnswer(intent);

    try {
      await supabase.from("conversations").insert({
        user_id,
        question,
        reponse: shortenText(fallbackAnswer, 20000),
        from_cache: false,
      });
    } catch {
      // ignore
    }

    return new Response(JSON.stringify({
      answer: fallbackAnswer,
      from_cache: false,
      degraded: true
    }), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});