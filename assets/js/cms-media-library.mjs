// Mr XPRONOS — Admin-only media library. Public URLs are display-only.
import { isSafeCmsUrl } from "./cms-url-guard.mjs";
import { cloudflareCmsMediaApiUrl,neonPublicMediaUrl } from "./config.js";
const BUCKET="cms-media";
export const MIME_EXT=Object.freeze({
  "image/jpeg":"jpg","image/png":"png","image/webp":"webp","image/gif":"gif",
  "video/mp4":"mp4","video/webm":"webm"
});
export function checkCmsFile(file,bytes){
  const mime=String(file?.type||"").toLowerCase(), size=Number(file?.size||0);
  if(!Object.hasOwn(MIME_EXT,mime))throw Error("Format non pris en charge : JPEG, PNG, WebP, GIF, MP4 ou WebM.");
  const max=mime.startsWith("image/")?15*1024*1024:30*1024*1024;
  if(!Number.isFinite(size)||size<1||size>max)throw Error("Fichier trop volumineux : limite "+(max/1048576)+" Mo.");
  const b=bytes instanceof Uint8Array?bytes:new Uint8Array(bytes||[]);
  const ascii=(i,n)=>String.fromCharCode(...b.slice(i,i+n));
  const valid=mime==="image/jpeg" ? b[0]===255&&b[1]===216&&b[2]===255 :
    mime==="image/png" ? ascii(1,3)==="PNG"&&b[0]===137 :
    mime==="image/webp" ? ascii(0,4)==="RIFF"&&ascii(8,4)==="WEBP" :
    mime==="image/gif" ? ["GIF87a","GIF89a"].includes(ascii(0,6)) :
    mime==="video/mp4" ? ascii(4,4)==="ftyp" :
    b[0]===26&&b[1]===69&&b[2]===223&&b[3]===163;
  if(!valid)throw Error("Signature binaire non cohérente avec le type déclaré.");
  return {mime,size,kind:mime.startsWith("image/")?"image":"video",ext:MIME_EXT[mime]};
}
function el(tag,text="",cls=""){
  const node=document.createElement(tag);node.textContent=text;if(cls)node.className=cls;return node;
}
function canvasBlob(img,maxWidth,quality){
  const scale=Math.min(1,maxWidth/img.width);
  const canvas=document.createElement("canvas");
  canvas.width=Math.max(1,Math.round(img.width*scale));
  canvas.height=Math.max(1,Math.round(img.height*scale));
  canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height);
  return new Promise((resolve,reject)=>canvas.toBlob(blob=>
    blob?resolve({blob,width:canvas.width,height:canvas.height}):reject(Error("Compression impossible")),
    "image/webp",quality));
}
async function optimizeImage(file,mime){
  if(mime==="image/gif")return {file,width:null,height:null,thumbnail:null};
  const url=URL.createObjectURL(file);
  try{
    const image=new Image();image.src=url;
    await image.decode();
    const full=await canvasBlob(image,1600,0.82);
    if(full.blob.size>8*1048576)throw Error("Image optimisée encore supérieure à 8 Mo");
    const thumbnail=await canvasBlob(image,420,0.72);
    return {file:full.blob,width:full.width,height:full.height,thumbnail:thumbnail.blob,
      mime:"image/webp",ext:"webp"};
  }finally{URL.revokeObjectURL(url);}
}
function publicMediaUrl(key) {
  if(!/^cms\/[0-9a-f-]{36}\.(jpg|png|webp|gif|mp4|webm)$/.test(String(key||"")))return null;
  return neonPublicMediaUrl.replace(/\/$/,"")+"/"+key;
}
async function mediaTransfer(sb,content,mime) {
  const {data:{session},error}=await sb.auth.getSession();
  if(error||!session?.access_token)throw Error("Session administrateur requise");
  if(!cloudflareCmsMediaApiUrl.startsWith("https://"))throw Error("Cloudflare média non déployé");
  const response=await fetch(cloudflareCmsMediaApiUrl+"/upload",{
    method:"POST",headers:{"Content-Type":mime,"Authorization":"Bearer "+session.access_token},
    body:content
  });
  const result=await response.json().catch(()=>({}));
  if(!response.ok||!result.key||!result.url)throw Error(result.error||"Upload Neon refusé");
  if(!isSafeCmsUrl(result.url,"image"))throw Error("URL publique incorrecte");
  return result;
}
async function removeMedia(sb,keys) {
  try{
    const {data:{session}}=await sb.auth.getSession();
    for(const key of keys){
      if(!key)continue;
      await fetch(cloudflareCmsMediaApiUrl+"/object?key="+encodeURIComponent(key),{
        method:"DELETE",headers:{"Authorization":"Bearer "+session.access_token}
      });
    }
  }catch(_) {/* Cleanup is best effort; server logs should track orphans. */}
}
export async function uploadCmsFile(sb,file,alt="",caption=""){
  if(!file||typeof file.slice!=="function")throw Error("Sélectionne un fichier.");
  const signature=new Uint8Array(await file.slice(0,16).arrayBuffer());
  const check=checkCmsFile(file,signature);
  if(check.kind==="image"&&!String(alt).trim())throw Error("Texte alternatif obligatoire pour les images.");
  const {data:{user},error:userErr}=await sb.auth.getUser();
  if(userErr||!user?.id)throw Error("Session administrateur absente");
  const transformed=check.kind==="image"?await optimizeImage(file,check.mime):
    {file,thumbnail:null,width:null,height:null};
  const mime=transformed.mime||check.mime;
  const main=await mediaTransfer(sb,transformed.file,mime);
  let thumb=null;
  try{
    if(transformed.thumbnail)thumb=await mediaTransfer(sb,transformed.thumbnail,"image/webp");
    const row={storage_path:main.key,kind:check.kind,mime_type:mime,
      original_name:String(file.name||"media").slice(0,240),file_size:transformed.file.size,
      width:transformed.width||null,height:transformed.height||null,
      alt_text:String(alt).slice(0,300),caption:String(caption).slice(0,1000),
      thumbnail_path:thumb?.key||null};
    const {data,error}=await sb.from("cms_media").insert(row).select("*").single();
    if(error)throw new Error(error.message||String(error));
    return {...data,url:main.url,thumbUrl:thumb?.url||null};
  }catch(error){
    await removeMedia(sb,[main.key,thumb?.key]);
    throw error;
  }
}
export async function listCmsMedia(sb,{offset=0,pageSize=48}={}){
  if(!Number.isInteger(offset)||offset<0||!Number.isInteger(pageSize)||pageSize<1||pageSize>100)
    throw Error("Pagination média invalide");
  const {data,error}=await sb.from("cms_media").select(
    "id,kind,storage_path,mime_type,alt_text,caption,thumbnail_path,created_at,original_name"
  ).order("created_at",{ascending:false}).range(offset,offset+pageSize-1);
  if(error)throw error;
  return (data||[]).map(row=>({
    ...row,url:publicMediaUrl(row.storage_path),
    thumbUrl:row.thumbnail_path?publicMediaUrl(row.thumbnail_path):null
  }));
}

export function filterCmsMedia(items,{search="",kind="all"}={}){
  const norm=x=>String(x??"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim();
  const query=norm(search);
  return (Array.isArray(items)?items:[]).filter(item=>{
    if(!item||typeof item!=="object")return false;
    if(kind!=="all"&&item.kind!==kind)return false;
    const text=[item.original_name,item.alt_text,item.caption,item.mime_type].map(norm).join(" ");
    return !query||text.includes(query);
  });
}

export function mountCmsMediaPicker(sb,container,onSelect,{defaultKind="all"}={}){
  const holder=el("section","","mx-cms-library"),status=el("p","","muted");
  const heading=el("h4","Médiathèque");
  const alt=el("input"),caption=el("input"),file=el("input"),upload=el("button","Importer"),
    refresh=el("button","Actualiser"),grid=el("div","","mx-media-grid");
  const browse=el("div","","mx-media-filters"),search=el("input"),kind=el("select"),
    more=el("button","Charger les médias suivants");
  const pageSize=48;
  let loaded=[],hasMore=false,loading=false,generation=0;
  alt.placeholder="Description de l’image (obligatoire)";
  alt.setAttribute("aria-label","Texte alternatif");
  caption.placeholder="Légende facultative";
  file.type="file";file.accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm";
  search.type="search";search.placeholder="Rechercher parmi les médias chargés";
  search.setAttribute("aria-label","Rechercher des médias");
  kind.setAttribute("aria-label","Filtrer les médias");
  for(const [value,label] of [["all","Images et vidéos"],["image","Images uniquement"],["video","Vidéos uniquement"]]){
    const option=el("option",label);option.value=value;kind.appendChild(option);
  }
  kind.value=["all","image","video"].includes(defaultKind)?defaultKind:"all";
  upload.type="button";refresh.type="button";more.type="button";
  more.hidden=true;
  browse.append(search,kind);
  holder.append(heading,alt,caption,file,upload,refresh,browse,status,grid,more);
  container.appendChild(holder);
  function render(){
    const filtered=filterCmsMedia(loaded,{search:search.value,kind:kind.value});
    grid.replaceChildren();
    for(const m of filtered){
      const item=el("button","","mx-media-item");item.type="button";
      if(m.kind==="image"&&isSafeCmsUrl(m.thumbUrl||m.url,"image")){
        const img=document.createElement("img");img.src=m.thumbUrl||m.url;
        img.alt=m.alt_text||m.original_name;img.loading="lazy";item.appendChild(img);
      }else item.appendChild(el("span","Vidéo"));
      item.appendChild(el("span",m.caption||m.original_name));
      item.addEventListener("click",()=>onSelect?.(m));
      grid.appendChild(item);
    }
    status.textContent=`${filtered.length} résultat(s) parmi ${loaded.length} média(s) chargés. ${hasMore?"D’autres médias peuvent être chargés.":"Fin des médias disponibles."}`;
    more.hidden=!hasMore;
    more.disabled=loading;
  }
  async function fetchNext(){
    if(loading||!hasMore)return;
    loading=true;more.disabled=true;
    const current=generation,offset=loaded.length;
    try{
      const rows=await listCmsMedia(sb,{offset,pageSize});
      if(current!==generation)return;
      loaded.push(...rows);
      hasMore=rows.length===pageSize;
    }catch(error){
      if(current===generation)status.textContent="Chargement impossible : "+error.message;
      return;
    }finally{
      if(current===generation){
        loading=false;
        const errorText=status.textContent.startsWith("Chargement impossible")?status.textContent:null;
        render();
        if(errorText)status.textContent=errorText;
      }
    }
  }
  async function reload(){
    generation++;loaded=[];hasMore=true;loading=false;
    grid.replaceChildren();status.textContent="Chargement des médias…";
    await fetchNext();
  }
  upload.addEventListener("click",async()=>{
    upload.disabled=true;status.textContent="Vérification et import du média…";
    try{
      const m=await uploadCmsFile(sb,file.files?.[0],alt.value,caption.value);
      file.value="";await reload();onSelect?.(m);
    }catch(error){status.textContent="Échec : "+error.message;}
    finally{upload.disabled=false;}
  });
  refresh.addEventListener("click",()=>void reload());
  more.addEventListener("click",()=>void fetchNext());
  for(const control of [search,kind])control.addEventListener("input",render);
  void reload();
  return {refresh:reload,root:holder};
}

export function mountCmsMediaFieldPicker(sb,input,{onlyKind="image"}={}){
  if(!input?.parentElement)return null;
  const toggle=el("button","Importer / médiathèque"),panel=el("div");
  toggle.type="button";panel.hidden=true;
  input.after(toggle,panel);
  toggle.addEventListener("click",()=>{panel.hidden=!panel.hidden;});
  const library=mountCmsMediaPicker(sb,panel,media=>{
    if(media.kind!==onlyKind)return;
    input.value=media.url;input.dispatchEvent(new Event("input",{bubbles:true}));
    panel.hidden=true;
  },{defaultKind:onlyKind});
  return library;
}
