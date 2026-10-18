import { serve } from "https://deno.land/std@0.170.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { inspectPublishFiles } from "./guards.mjs";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const GITHUB_OWNER = Deno.env.get("GITHUB_OWNER") || "";
const GITHUB_REPO = Deno.env.get("GITHUB_REPO") || "";
const GITHUB_BRANCH = Deno.env.get("GITHUB_BRANCH") || "main";
const GITHUB_PAT = Deno.env.get("GITHUB_PAT") || "";

// Optionnel: limiter l'origine CORS si tu veux (sinon *)
const ALLOW_ORIGIN = Deno.env.get("PUBLISH_CORS_ORIGIN") || "*";

const corsHeaders = {
  "Access-Control-Allow-Origin": ALLOW_ORIGIN,
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, apikey",
};

const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function nowIso() {
  return new Date().toISOString();
}

// Base64 UTF-8 safe (Deno)
function toBase64Utf8(s: string) {
  const bytes = new TextEncoder().encode(s);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

async function requireAdmin(req: Request) {
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
    throw new Error("Server misconfigured: missing Supabase env");
  }

  const auth = req.headers.get("Authorization") || "";
  const token = auth.toLowerCase().startsWith("bearer ")
    ? auth.slice(7).trim()
    : "";

  if (!token) {
    const err: any = new Error("Missing bearer token");
    err.code = 401;
    throw err;
  }

  const { data, error } = await sb.auth.getUser(token);
  if (error || !data?.user) {
    const err: any = new Error("Invalid session");
    err.code = 401;
    throw err;
  }

  const uid = data.user.id;

  // Vérification admin par table
  const { data: adminRow, error: adminErr } = await sb
    .from("admin_users")
    .select("user_id, active")
    .eq("user_id", uid)
    .maybeSingle();

  if (adminErr) throw adminErr;
  if (!adminRow || adminRow.active !== true) {
    const err: any = new Error("not_admin");
    err.code = 403;
    throw err;
  }

  return uid;
}

function ghHeaders() {
  return {
    "Authorization": `Bearer ${GITHUB_PAT}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "mrxpronos-publish-bot",
  };
}

async function ghJson(path: string, method = "GET", body?: unknown) {
  const response = await fetch("https://api.github.com/repos/" + encodeURIComponent(GITHUB_OWNER) + "/" + encodeURIComponent(GITHUB_REPO) + path, {
    method, headers: { ...ghHeaders(), "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    // Keep private response payload and token out of the client-visible error.
    throw new Error("GitHub publication: " + method + " " + path.split("?")[0] + " HTTP " + response.status);
  }
  return response.json();
}
async function ghPublishAtomic(files: Record<string,string>, stamp: string, expectedHead?:string): Promise<string> {
  if (!GITHUB_OWNER || !GITHUB_REPO || !GITHUB_PAT || !GITHUB_BRANCH)
    throw new Error("Configuration GitHub incomplète");
  if (Object.keys(files).length !== 5) throw new Error("Publication incomplète");
  const branchEncoded = GITHUB_BRANCH.split("/").map(encodeURIComponent).join("/");
  const branch = await ghJson("/git/ref/heads/" + branchEncoded);
  const baseSha = branch?.object?.sha;
  if (!/^[a-f0-9]{40}$/i.test(String(baseSha))) throw new Error("Référence GitHub invalide");
  if(expectedHead && baseSha !== expectedHead) throw Object.assign(new Error("La branche a évolué depuis la prévisualisation"),{code:409});
  const baseCommit = await ghJson("/git/commits/" + baseSha);
  const entries = [];
  for (const [path, content] of Object.entries(files)) {
    const blob = await ghJson("/git/blobs", "POST", { content: toBase64Utf8(content), encoding: "base64" });
    entries.push({path, mode:"100644", type:"blob", sha:blob.sha});
  }
  const tree = await ghJson("/git/trees", "POST", {base_tree:baseCommit.tree.sha, tree:entries});
  const commit = await ghJson("/git/commits", "POST", {
    message:"CMS publish " + stamp, tree:tree.sha, parents:[baseSha]
  });
  // A concurrent GitHub push fails safely (non-fast-forward), instead of silently overwriting it.
  await ghJson("/git/refs/heads/" + branchEncoded, "PATCH", {sha:commit.sha, force:false});
  return commit.sha;
}


const cmsFiles=["articles.json","conseils.json","bonus.json","infos.json","bookmakers.json"];
const isSha=(s:any)=>/^[0-9a-f]{40}$/i.test(String(s||""));
const isUuid=(s:any)=>/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(String(s||""));
const bad=(message:string,code=400)=>Object.assign(new Error(message),{code});
async function cmsVersion(id:any) {
  if(!isUuid(id)) throw bad("Version invalide");
  const {data,error}=await sb.from("publish_history").select("id,created_at,payload").eq("id",String(id)).maybeSingle();
  if(error) throw error;
  if(!data||!isSha(data.payload?.github_commit)) throw bad("Version introuvable",404);
  return data;
}
async function cmsHead() {
  const branch=GITHUB_BRANCH.split("/").map(encodeURIComponent).join("/");
  const sha=(await ghJson("/git/ref/heads/"+branch))?.object?.sha;
  if(!isSha(sha)) throw bad("Référence GitHub invalide",502);
  return String(sha);
}
async function cmsJson(path:string,ref:string) {
  if(!cmsFiles.includes(path)) throw bad("Fichier interdit");
  const item=await ghJson("/contents/"+encodeURIComponent(path)+"?ref="+encodeURIComponent(ref));
  if(item?.type!=="file"||item?.encoding!=="base64"||!item.content) throw bad("Fichier GitHub illisible : "+path,502);
  const bin=Uint8Array.from(atob(String(item.content).replace(/\s/g,"")),(x)=>x.charCodeAt(0));
  const raw=new TextDecoder().decode(bin);
  let data:any;
  try {data=JSON.parse(raw);} catch {throw bad("Contenu JSON invalide : "+path,502);}
  if(!Array.isArray(data)) throw bad("Tableau JSON attendu : "+path,502);
  return {raw,data,blob:item.sha};
}
function cmsDifference(current:any[],target:any[]) {
  const identity=(v:any,i:number)=>String(v?.slug||v?.bookmaker||v?.name||v?.title||"index:"+i);
  const first=new Map(current.map((v,i)=>[identity(v,i),JSON.stringify(v)]));
  const second=new Map(target.map((v,i)=>[identity(v,i),JSON.stringify(v)]));
  const added=[...second.keys()].filter(k=>!first.has(k));
  const removed=[...first.keys()].filter(k=>!second.has(k));
  const modified=[...second.keys()].filter(k=>first.has(k)&&first.get(k)!==second.get(k));
  return {before:current.length,after:target.length,added:added.length,removed:removed.length,
    modified:modified.length,samples:{added:added.slice(0,5),removed:removed.slice(0,5),modified:modified.slice(0,5)}};
}
async function cmsPreview(id:any) {
  const history=await cmsVersion(id),target=String(history.payload.github_commit),head=await cmsHead();
  const changes:Record<string,any>={};
  for(const path of cmsFiles){
    const [from,to]=await Promise.all([cmsJson(path,head),cmsJson(path,target)]);
    changes[path]={...cmsDifference(from.data,to.data),different:from.blob!==to.blob};
  }
  return {version_id:history.id,current_head:head,target_commit:target,changes};
}
async function cmsSeal(uid:string,p:any,expiry:number) {
  const value=[uid,p.version_id,p.target_commit,p.current_head,expiry].join(":");
  const key=await crypto.subtle.importKey("raw",new TextEncoder().encode(SUPABASE_SERVICE_ROLE_KEY),
    {name:"HMAC",hash:"SHA-256"},false,["sign"]);
  return Array.from(new Uint8Array(await crypto.subtle.sign("HMAC",key,new TextEncoder().encode(value))))
    .map(x=>x.toString(16).padStart(2,"0")).join("");
}
// The stamp binds an authenticated admin to the exact CMS snapshot, branch HEAD and deadline.
async function cmsPublishSeal(uid:string,head:string,files:Record<string,string>,expires:number) {
  const ordered=cmsFiles.map(path=>files[path]).join("\u001e");
  const hash=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(ordered));
  const hex=Array.from(new Uint8Array(hash)).map(b=>b.toString(16).padStart(2,"0")).join("");
  return cmsSeal(uid,{version_id:"publish",target_commit:hex,current_head:head},expires);
}
async function cmsInspectAtHead(head:string,files:Record<string,string>) {
  const pairs=await Promise.all(cmsFiles.map(async path=>[path,(await cmsJson(path,head)).raw] as const));
  return inspectPublishFiles(files,Object.fromEntries(pairs));
}

async function cmsRestore(uid:string,body:any) {
  if(body?.confirm!=="RESTAURER") throw bad("Confirmation explicite manquante");
  const expiry=Number(body.preview_expires);
  if(!Number.isSafeInteger(expiry)||expiry<Date.now()||expiry>Date.now()+300000) throw bad("Prévisualisation expirée",409);
  const p=await cmsPreview(body.version_id);
  if(p.current_head!==String(body.expected_head||"")) throw bad("Le dépôt a évolué : nouvelle prévisualisation nécessaire",409);
  if(await cmsSeal(uid,p,expiry)!==body.preview_signature) throw bad("Signature de prévisualisation invalide",403);
  if(!Object.values(p.changes).some((c:any)=>c.different)) throw bad("Aucun changement à restaurer",409);
  const files:Record<string,string>={};
  for(const path of cmsFiles)files[path]=(await cmsJson(path,p.target_commit)).raw;
  const commit=await ghPublishAtomic(files,"RESTORE "+nowIso()+" "+p.target_commit.slice(0,12),p.current_head);
  const payload={operation:"restore",github_commit:commit,restored_from:p.target_commit,restored_version_id:p.version_id,
    files:cmsFiles,status:"committed",deployment:"pending",published_at:nowIso()};
  const {error:histError}=await sb.from("publish_history").insert({actor_user_id:uid,payload});
  if(histError) {console.error("Restore history",histError.code);throw new Error("Commit de restauration créé mais historique non enregistré : "+commit);}
  const {error:auditError}=await sb.from("audit_log").insert({actor_user_id:uid,action:"restore_json",
    details:{github_commit:commit,restored_from:p.target_commit,files:cmsFiles}});
  if(auditError) console.error("Restore audit",auditError.code);
  return {success:true,status:"committed",deployment:"pending",github_commit:commit,restored_from:p.target_commit};
}

function isBonusActive(b: any) {
  const now = new Date();
  const s = b?.start_date ? new Date(b.start_date + "T00:00:00") : null;
  const e = b?.end_date ? new Date(b.end_date + "T23:59:59") : null;
  if (s && now < s) return false;
  if (e && now > e) return false;
  return true;
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    if (req.method !== "POST") return json({ error: "Method not allowed" }, 405);

    const actorUid = await requireAdmin(req);
    const requestBody = await req.json().catch(() => ({}));
    if (requestBody?.operation === "status") {
      const sha=String(requestBody?.commit||"").trim();
      if(!/^[0-9a-f]{40}$/i.test(sha)) return json({error:"Commit GitHub invalide"},400);
      const {data:version,error:versionError}=await sb.from("publish_history")
        .select("id,payload").contains("payload",{github_commit:sha}).limit(1).maybeSingle();
      if(versionError) throw versionError;
      if(!version) return json({error:"Commit non enregistré dans l'historique"},404);
      const [runsResult,deployments]=await Promise.all([
        ghJson("/actions/runs?head_sha="+encodeURIComponent(sha)+"&per_page=100"),
        ghJson("/deployments?sha="+encodeURIComponent(sha)+"&environment=github-pages&per_page=20")
      ]);
      const pagesRuns=(runsResult.workflow_runs||[]).filter((run:any)=>
        run.head_sha===sha && /pages|deploy.*site|deploy.*web/i.test(String(run.name||"")+" "+String(run.path||"")));
      pagesRuns.sort((a:any,b:any)=>String(b.created_at||"").localeCompare(String(a.created_at||"")));
      const run=pagesRuns[0];
      let deployment="unknown";
      let workflow_url=run?.html_url||null;
      for(const d of Array.isArray(deployments)?deployments:[]) {
        if(d.sha!==sha || d.environment!=="github-pages") continue;
        const states=await ghJson("/deployments/"+d.id+"/statuses?per_page=10");
        const latest=Array.isArray(states)?states[0]:null;
        if(!latest) continue;
        deployment=latest.state==="success"?"deployed":
          ["failure","error"].includes(latest.state)?"failed":"pending";
        workflow_url=latest.log_url||workflow_url;
        break;
      }
      if(deployment==="unknown"&&run) {
        deployment=run.status!=="completed"?"pending":run.conclusion==="success"?"deployed":
          ["failure","cancelled","timed_out","action_required"].includes(run.conclusion)?"failed":"unknown";
      }
      const gitBranch=GITHUB_BRANCH.split("/").map(encodeURIComponent).join("/");
      const head=(await ghJson("/git/ref/heads/"+gitBranch)).object?.sha;
      const current=head===sha;
      const status=deployment==="deployed"?"deployed":
        deployment==="failed"?"deployment_failed":deployment==="pending"?"deployment_in_progress":"deployment_unknown";
      if(version.payload?.status!==status) {
        const {error:historyError}=await sb.from("publish_history")
          .update({payload:{...version.payload,status,deployment,last_checked_at:nowIso()}}).eq("id",version.id);
        if(historyError) console.error("Publication state persistence error",historyError.code);
        const {error:auditError}=await sb.from("audit_log").insert({
          actor_user_id:actorUid,action:"publish_deployment_state",details:{github_commit:sha,status}});
        if(auditError) console.error("Publication status audit error",auditError.code);
      }
      return json({success:true,github_commit:sha,status,deployment,is_current:current,workflow_url});
    }
    if(requestBody?.operation==="history") {
      const {data,error}=await sb.from("publish_history").select("id,created_at,payload")
        .order("created_at",{ascending:false}).limit(30);
      if(error) throw error;
      return json({success:true,versions:(data||[]).filter((v:any)=>
        /^[0-9a-f]{40}$/i.test(String(v.payload?.github_commit||""))).map((v:any)=>({
          id:v.id,date:v.created_at,github_commit:v.payload.github_commit,
          status:v.payload.status||"committed",deployment:v.payload.deployment||"unknown",
          operation:v.payload.operation||"publish",counts:v.payload.counts||null}))});
    }
    if(requestBody?.operation==="preview_restore"){
      const preview=await cmsPreview(requestBody.version_id),expires=Date.now()+300000;
      return json({success:true,preview:{...preview,preview_expires:expires,preview_signature:await cmsSeal(actorUid,preview,expires)}});
    }
    if(requestBody?.operation==="restore") return json(await cmsRestore(actorUid,requestBody));
    if (requestBody?.operation && !["publish","preflight"].includes(requestBody.operation)) return json({error:"Opération inconnue"},400);


    // ARTICLES
    const { data: articles, error: aErr } = await sb
      .from("cms_articles")
      .select("*")
      .eq("status", "published")
      .order("published_at", { ascending: false });

    if (aErr) throw aErr;

    const articlesJson = (articles || []).map((a: any) => ({
      slug: a.slug,
      title: a.title,
      date: (a.published_at || a.updated_at || nowIso()),
      author: a.author || "Mr XPRONOS",
      excerpt: a.excerpt || "",
      meta_description: a.meta_description || "",
      keywords: a.keywords || "",
      faq: a.faq || [],
      content: a.content || "",
      image_url: a.image_url || "",
      og_image: a.og_image || a.image_url || "",
      active: a.active !== false,
    }));

    // CONSEILS
    const { data: conseils, error: cErr } = await sb
      .from("cms_conseils")
      .select("*")
      .eq("status", "published")
      .order("published_at", { ascending: false });

    if (cErr) throw cErr;

    const conseilsJson = (conseils || []).map((c: any) => ({
      slug: c.slug,
      title: c.title,
      content: c.content || "",
      date: (c.published_at || c.updated_at || nowIso()),
      excerpt: c.excerpt || "",
      image_url: c.image_url || "",
      active: c.active !== false,
      keywords: c.keywords || "",
    }));

    // BONUS (✅ filtrés par dates + active)
    const { data: bonus, error: bErr } = await sb
      .from("cms_bonus")
      .select("*")
      .eq("status", "published")
      .order("published_at", { ascending: false });

    if (bErr) throw bErr;

    const bonusJson = (bonus || [])
      .filter((b: any) => (b.active !== false) && isBonusActive(b))
      .map((b: any) => ({
        bookmaker: b.bookmaker,
        title: b.title,
        description: b.description,
        image: b.image_url || "",
        link: b.link || "",
        footer: b.footer || "",
        start_date: b.start_date || null,
        end_date: b.end_date || null,
        active: true,
      }));

    // INFOS
    const { data: infos, error: iErr } = await sb
      .from("cms_infos")
      .select("*")
      .eq("status", "published")
      .order("published_at", { ascending: false });

    if (iErr) throw iErr;

    const infosJson = (infos || []).map((i: any) => ({
      title: i.title,
      content: i.content,
      date: (i.published_at || i.updated_at || nowIso()),
      active: i.active !== false,
    }));

    // BOOKMAKERS
    const { data: books, error: bkErr } = await sb
      .from("cms_bookmakers")
      .select("*")
      .eq("status", "published")
      .order("updated_at", { ascending: false });

    if (bkErr) throw bkErr;

    const bookmakersJson = (books || []).map((b: any) => ({
      name: b.name,
      logo: b.logo || "",
      url: b.url || "",
      description: b.description || "",
      active: b.active !== false,
    }));

    // Prepare all five files before allowing any repository mutation.
    const files:Record<string,string>={
      "articles.json": JSON.stringify(articlesJson,null,2),
      "conseils.json": JSON.stringify(conseilsJson,null,2),
      "bonus.json": JSON.stringify(bonusJson,null,2),
      "infos.json": JSON.stringify(infosJson,null,2),
      "bookmakers.json": JSON.stringify(bookmakersJson,null,2),
    };
    const head=await cmsHead();
    const inspection=await cmsInspectAtHead(head,files);
    const counts={
      articles:articlesJson.length,conseils:conseilsJson.length,bonus:bonusJson.length,
      infos:infosJson.length,bookmakers:bookmakersJson.length
    };
    if(requestBody?.operation==="preflight"){
      const expires=Date.now()+300000;
      return json({success:true,preview:{...inspection,current_head:head,
        counts,preflight_expires:expires,
        preflight_signature:await cmsPublishSeal(actorUid,head,files,expires)}});
    }
    if(!inspection.has_changes){
      return json({success:true,skipped:true,status:"unchanged",github_commit:head,
        deployment:"unchanged",counts});
    }
    const expiry=Number(requestBody?.preflight_expires);
    if(!Number.isSafeInteger(expiry)||expiry<Date.now()||expiry>Date.now()+300000)
      throw bad("Prévisualisation de publication expirée",409);
    if(requestBody?.expected_head!==head)
      throw bad("La branche GitHub a changé; prévisualisez à nouveau",409);
    if(await cmsPublishSeal(actorUid,head,files,expiry)!==requestBody?.preflight_signature)
      throw bad("Prévisualisation non authentifiée ou données CMS modifiées",403);
    if(inspection.emptied_files.length && requestBody?.acknowledge_empty!=="PUBLIER VIDE")
      throw bad("Confirmation spéciale obligatoire pour vider un contenu existant",409);
    // A concurrent push must fail rather than overwrite the new branch head.
    const stamp=nowIso();
    const publishedCommit = await ghPublishAtomic(files,stamp,head);

    // HISTORY + AUDIT (✅ plus léger : pas le payload complet)
    const { error: historyError } = await sb.from("publish_history").insert({
      actor_user_id: actorUid,
      payload: {
        files: ["articles.json","conseils.json","bonus.json","infos.json","bookmakers.json"],
        counts: {
          articles: articlesJson.length,
          conseils: conseilsJson.length,
          bonus: bonusJson.length,
          infos: infosJson.length,
          bookmakers: bookmakersJson.length,
        },
        published_at: nowIso(),
        operation: "publish",
        github_commit: publishedCommit,
        deployment: "pending",
        status: "committed",
      }
    });
    if (historyError) { console.error("CMS publish_history insert failed",historyError.code); throw new Error("Commit créé mais historique non enregistré : "+publishedCommit); }
    const { error: auditError } = await sb.from("audit_log").insert({
      actor_user_id: actorUid,
      action: "publish_json",
      details: {
        github_commit: publishedCommit,
        status: "committed",
        files: ["articles.json","conseils.json","bonus.json","infos.json","bookmakers.json"],
        counts: {
          articles: articlesJson.length,
          conseils: conseilsJson.length,
          bonus: bonusJson.length,
          infos: infosJson.length,
          bookmakers: bookmakersJson.length,
        },
      },
    });

    if (auditError) throw new Error("Publication appliquée mais audit non enregistré: "+auditError.message);
    return json({
      success: true,
      github_commit: publishedCommit,
      status: "committed",
      deployment: "pending",
      counts: {
        articles: articlesJson.length,
        conseils: conseilsJson.length,
        bonus: bonusJson.length,
        infos: infosJson.length,
        bookmakers: bookmakersJson.length,
      },
    });

  } catch (e: any) {
    const msg = e?.message || String(e);
    const code = e?.code && Number.isFinite(e.code) ? e.code : (
      msg === "not_admin" ? 403 :
      msg.toLowerCase().includes("token") ? 401 :
      500
    );
    return json({ error: msg }, code);
  }
});