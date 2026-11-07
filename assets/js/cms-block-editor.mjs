// A block authoring layer that keeps the existing Markdown CMS field as its source of truth.
import {mountCmsMediaPicker} from "./cms-media-library.mjs";
import {isSafeCmsUrl} from "./cms-url-guard.mjs";
import {createServerDraftStore} from "./admin-draft-sync.mjs";
const TYPES=["paragraph","heading","subheading","bullets","quote","image","video","link","table","raw"];
const LABELS={paragraph:"Paragraphe",heading:"Titre H2",subheading:"Sous-titre H3",
 bullets:"Liste",quote:"Citation",image:"Image",video:"Vidéo",link:"Lien",table:"Tableau",raw:"Source brute"};
const text=x=>String(x??"");
const esc=x=>text(x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
export function parseCmsMarkdown(markdown){
  const value=text(markdown).trim();
  if(!value)return [{type:"paragraph",value:"",url:"",alt:""}];
  return value.split(/\n\s*\n/).map(chunk=>{
    let match;
    if((match=chunk.match(/^## (?!#)([\s\S]*)$/)))return {type:"heading",value:match[1],url:"",alt:""};
    if((match=chunk.match(/^### ([\s\S]*)$/)))return {type:"subheading",value:match[1],url:"",alt:""};
    if((match=chunk.match(/^!\[([^\]]*)\]\((https?:[^\s)]+)\)$/)))
      return {type:"image",value:"",url:match[2],alt:match[1]};
    if((match=chunk.match(/^<video\s+[^>]*src="([^"]+)"[^>]*><\/video>$/)))
      return {type:"video",value:"",url:match[1],alt:""};
    if((match=chunk.match(/^\[([^\]]+)\]\(([^)]+)\)$/)))
      return {type:"link",value:match[1],url:match[2],alt:""};
    if(chunk.split("\n").every(line=>/^\s*[-*] /.test(line)))
      return {type:"bullets",value:chunk.replace(/^\s*[-*] /gm,""),url:"",alt:""};
    if(chunk.split("\n").every(line=>/^>\s?/.test(line)))
      return {type:"quote",value:chunk.replace(/^>\s?/gm,""),url:"",alt:""};
    if(/^\|.+\|[\r\n]/.test(chunk))return {type:"table",value:chunk,url:"",alt:""};
    if(/<\/?[a-z][^>]*>|^```/.test(chunk))
      return {type:"raw",value:chunk,url:"",alt:""};
    return {type:"paragraph",value:chunk,url:"",alt:""};
  });
}
function safeInline(value){return text(value).replace(/[\r\n]/g," ").trim();}
export function serializeCmsBlocks(blocks){
  if(!Array.isArray(blocks)||blocks.length>150)throw Error("Trop de blocs");
  return blocks.map(block=>{
    const type=block.type||"paragraph",value=text(block.value),url=text(block.url).trim(),alt=safeInline(block.alt);
    if(!TYPES.includes(type))throw Error("Type de bloc invalide");
    if(type==="heading")return "## "+safeInline(value);
    if(type==="subheading")return "### "+safeInline(value);
    if(type==="bullets")return value.split("\n").map(line=>"- "+line.replace(/^[-*]\s*/,"")).join("\n");
    if(type==="quote")return value.split("\n").map(line=>"> "+line.replace(/^>\s?/,"")).join("\n");
    if(type==="image"){
      if(!isSafeCmsUrl(url,"image"))throw Error("URL de l'image invalide");
      if(!alt)throw Error("Texte alternatif de l'image manquant");
      return `![${alt.replace(/[\[\]]/g,"")}](${url})`;
    }
    if(type==="video"){
      if(!isSafeCmsUrl(url,"image")||!/^https:\/\//i.test(url))throw Error("Vidéo HTTPS requise");
      return `<video controls preload="metadata" playsinline src="${esc(url)}"></video>`;
    }
    if(type==="link"){
      if(!isSafeCmsUrl(url,"link"))throw Error("Lien invalide");
      return `[${safeInline(value).replace(/[\[\]]/g,"")}](${url})`;
    }
    return value;
  }).filter(Boolean).join("\n\n");
}
function node(tag,content="",className=""){
  const el=document.createElement(tag);if(content)el.textContent=content;
  if(className)el.className=className;return el;
}
export function mountCmsBlockEditor({sb,textarea,kind,identity="new"}){
  if(!textarea||!sb)throw Error("Éditeur : configuration manquante");
  const editor=node("div","","mx-block-editor"),toolbar=node("div","","mx-block-toolbar");
  const addType=node("select"),add=node("button","Ajouter un bloc"),previewBtn=node("button","Prévisualiser"),
    sourceBtn=node("button","Mode source"),recover=node("button","Récupérer un brouillon"),status=node("span","","muted");
  for(const type of TYPES){const option=node("option",LABELS[type]);option.value=type;addType.appendChild(option);}
  for(const b of [add,previewBtn,sourceBtn,recover])b.type="button";
  toolbar.append(addType,add,previewBtn,sourceBtn,recover,status);
  const list=node("div","","mx-block-list"),preview=node("section","","mx-block-preview");
  preview.hidden=true;preview.setAttribute("aria-label","Prévisualisation du contenu");
  const library=node("div","","mx-block-library");library.hidden=true;
  editor.append(toolbar,list,preview,library);textarea.after(editor);textarea.hidden=true;
  let blocks=parseCmsMarkdown(textarea.value),documentKey=String(identity);
  let dragging=-1,selectedBlock=-1,editGeneration=0;
  let saveTimer=null;
  let serverQueue=Promise.resolve();
  const serverStore=createServerDraftStore(sb,{kind,getIdentity:()=>documentKey,
    onStatus:message=>{status.textContent=message+" (non publié)";}});
  const draftKey=()=>`mx:cms:v2:${kind}:${documentKey}`;
  const queueDraftRead=key=>{
    serverQueue=serverQueue.catch(()=>{}).then(()=>serverStore.read(key)).catch(error=>{
      if(documentKey===key)status.textContent="Brouillons serveur indisponibles : "+String(error?.message||error);
    });
  };
  queueDraftRead(documentKey);
  const commit=()=>{
    textarea.value=serializeCmsBlocks(blocks);
    // Do not emit a synthetic input event here: source mode already listens for input.
    editGeneration+=1;
    status.textContent="Modifications non enregistrées";
    clearTimeout(saveTimer);
    saveTimer=setTimeout(()=>{
      const content=textarea.value,expectedKey=documentKey;
      if(content.length>150000){status.textContent="Brouillon trop long";return;}
      let localSaved=false;
      try{
        localStorage.setItem(draftKey(),JSON.stringify({at:Date.now(),content}));
        localSaved=true;
      }catch{ /* Private browsers may deny localStorage; still sync to server. */ }
      status.textContent=(localSaved?"Brouillon local enregistré":"Stockage local indisponible")+
        " · Synchronisation serveur…";
      serverQueue=serverQueue.catch(()=>{}).then(async()=>{
        if(documentKey!==expectedKey)return;
        try{await serverStore.save(content,expectedKey);}
        catch(e){
          if(documentKey===expectedKey)
            status.textContent=(localSaved?"Brouillon local conservé":"Brouillon non synchronisé")+
              " · Erreur serveur : "+String(e?.message||e);
        }
      });
    },1200);
  };
  const elementFor=(block,i)=>{
    const card=node("section","","mx-block-card");card.draggable=true;
    card.addEventListener("dragstart",e=>{dragging=i;e.dataTransfer?.setData("text/plain",String(i));});
    card.addEventListener("dragover",e=>e.preventDefault());
    card.addEventListener("drop",e=>{
      e.preventDefault();if(dragging<0||dragging===i)return;
      const moved=blocks.splice(dragging,1)[0];
      blocks.splice(i,0,moved);dragging=-1;render();commit();
    });
    const top=node("div","","mx-block-top"),grab=node("span","↕ Glisser","","");
    const kindSelect=node("select");
    for(const type of TYPES){const opt=node("option",LABELS[type]);opt.value=type;kindSelect.appendChild(opt);}
    kindSelect.value=block.type;
    kindSelect.addEventListener("change",()=>{block.type=kindSelect.value;render();commit();});
    const up=node("button","↑"),down=node("button","↓"),del=node("button","Supprimer");
    for(const b of [up,down,del])b.type="button";
    up.onclick=()=>{if(i>0){[blocks[i-1],blocks[i]]=[blocks[i],blocks[i-1]];render();commit();}};
    down.onclick=()=>{if(i<blocks.length-1){[blocks[i+1],blocks[i]]=[blocks[i],blocks[i+1]];render();commit();}};
    del.onclick=()=>{blocks.splice(i,1);if(!blocks.length)blocks.push({type:"paragraph",value:""});render();commit();};
    top.append(grab,kindSelect,up,down,del);card.appendChild(top);
    const input=node("textarea");input.rows=block.type==="raw"?7:3;
    input.placeholder=block.type==="table"?"| Colonne A | Colonne B |\n| --- | --- |\n| Valeur 1 | Valeur 2 |":"Saisir du texte…";
    input.value=block.value||"";
    input.addEventListener("input",()=>{block.value=input.value;try{commit();}catch(e){status.textContent=e.message;}});
    if(!["image","video"].includes(block.type))card.appendChild(input);
    if(["image","video","link"].includes(block.type)){
      const url=node("input");url.type="url";url.placeholder="https://…";url.value=block.url||"";
      url.addEventListener("input",()=>{block.url=url.value;try{commit();}catch(e){status.textContent=e.message;}});
      card.appendChild(url);
    }
    if(block.type==="image"){
      const alt=node("input");alt.placeholder="Description accessible de l'image";alt.value=block.alt||"";
      alt.addEventListener("input",()=>{block.alt=alt.value;try{commit();}catch(e){status.textContent=e.message;}});
      card.appendChild(alt);
    }
    if(["image","video"].includes(block.type)){
      const choose=node("button","Choisir dans la médiathèque");choose.type="button";
      choose.addEventListener("click",()=>{
        selectedBlock=i;library.hidden=false;library.scrollIntoView({behavior:"smooth",block:"nearest"});
      });
      card.appendChild(choose);
    }
    return card;
  };
  function render(){
    list.replaceChildren(...blocks.map((b,i)=>elementFor(b,i)));
  }
  // Sandbox preview with the same CSS as the public article detail page.
  // No scripts, forms, or network-origin privileges are granted to authored HTML.
  let previewMobile=true;
  const previewToolbar=node("div","","mx-preview-toolbar");
  const mobileButton=node("button","Mobile 390 px","btn btn-secondary");
  const desktopButton=node("button","Ordinateur","btn btn-secondary");
  for(const button of [mobileButton,desktopButton])button.type="button";
  const frame=node("iframe");frame.title="Aperçu de l'article (non publié)";
  frame.setAttribute("sandbox","");
  frame.setAttribute("referrerpolicy","no-referrer");
  frame.style.cssText="display:block;width:min(100%,390px);height:640px;max-width:100%;margin:12px auto;border:1px solid #526474;border-radius:10px;background:#0d1722";
  previewToolbar.append(mobileButton,desktopButton);
  preview.append(previewToolbar,frame);
  const htmlText=value=>text(value).replace(/[&<>"']/g,char=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[char]));
  function safePreviewHtml(){
    const parts=[];
    for(const b of blocks){
      const value=htmlText(b.value||"");
      const lines=value.split("\n").join("<br>");
      if(b.type==="heading")parts.push("<h2>"+lines+"</h2>");
      else if(b.type==="subheading")parts.push("<h3>"+lines+"</h3>");
      else if(b.type==="quote")parts.push("<blockquote>"+lines+"</blockquote>");
      else if(b.type==="bullets")parts.push("<ul>"+value.split("\n").map(v=>"<li>"+v+"</li>").join("")+"</ul>");
      else if(b.type==="image"&&isSafeCmsUrl(b.url,"image")){
        parts.push('<figure><img loading="lazy" alt="'+htmlText(b.alt)+'" src="'+htmlText(b.url)+'"><figcaption>'+htmlText(b.alt)+'</figcaption></figure>');
      } else if(b.type==="video"&&isSafeCmsUrl(b.url,"image")){
        parts.push('<video controls preload="none" playsinline src="'+htmlText(b.url)+'"></video>');
      } else if(b.type==="link"&&isSafeCmsUrl(b.url,"link"))
        parts.push('<p><a href="'+htmlText(b.url)+'">'+(lines||htmlText(b.url))+'</a></p>');
      else parts.push("<p>"+lines+"</p>");
    }
    return parts.join("\n");
  }
  function refreshPreview(){
    const base="https://mrxpronos.github.io/MrXPRONOS_App/";
    const contents=safePreviewHtml();
    frame.style.width=previewMobile?"min(100%,390px)":"100%";
    frame.srcdoc='<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
      +'<base href="'+base+'"><link rel="stylesheet" href="assets/css/style.css">'
      +'<link rel="stylesheet" href="assets/css/article-detail-premium.css">'
      +'<link rel="stylesheet" href="assets/css/site-typography.css">'
      +'<style>img,video{max-width:100%;height:auto}.article-content{overflow-wrap:anywhere}'
      +'.mx-reader-preview-label{color:#e9b650;font-size:12px;font-weight:700}'
      +'</style></head><body class="mx-article-detail-page">'
      +'<header class="mx-site-header"><div class="container mx-header-container">'
      +'<div class="logo"><img src="assets/images/mrxpronos-horizontal.webp" alt="Mr XPRONOS"></div>'
      +'</div></header><main class="container mx-article-detail-main"><div id="blog-post">'
      +'<article class="card article-page-card mx-reader-article">'
      +'<div class="mx-reader-meta"><span>Football</span><span class="mx-reader-preview-label">Non publié</span></div>'
      +'<h1>Aperçu de votre article</h1><div class="article-content">'
      +contents+'</div><div class="mx-reader-disclaimer">Cette analyse est informative. Les paris comportent un risque de perte.</div>'
      +'</article></div></main></body></html>';
  }
  mobileButton.onclick=()=>{previewMobile=true;refreshPreview();};
  desktopButton.onclick=()=>{previewMobile=false;refreshPreview();};
  add.onclick=()=>{
    blocks.push({type:addType.value,value:"",url:"",alt:""});
    render();commit();list.lastElementChild?.querySelector("textarea,input")?.focus();
  };
  previewBtn.onclick=()=>{preview.hidden=!preview.hidden;if(!preview.hidden)refreshPreview();};
  sourceBtn.onclick=()=>{
    textarea.hidden=!textarea.hidden;
    list.hidden=!textarea.hidden;
    sourceBtn.textContent=textarea.hidden?"Mode source":"Revenir aux blocs";
    if(textarea.hidden){blocks=parseCmsMarkdown(textarea.value);render();}
  };
  recover.onclick=async()=>{
    try{
      const server=await serverStore.read();
      const local=JSON.parse(localStorage.getItem(draftKey())||"null");
      const draft=server?.content!=null?server:local;
      if(!draft?.content){status.textContent="Aucun brouillon disponible";return;}
      if(!window.confirm("Restaurer le brouillon sauvegardé "+(server?"sur le serveur":"localement")+" ?"))return;
      textarea.value=draft.content;blocks=parseCmsMarkdown(draft.content);render();
      status.textContent="Brouillon restauré · Modifications non publiées";
    }catch(e){status.textContent="Impossible de récupérer le brouillon serveur : "+String(e?.message||e);}
  };
  textarea.addEventListener("input",()=>{if(!textarea.hidden){blocks=parseCmsMarkdown(textarea.value);commit();}});
  mountCmsMediaPicker(sb,library,media=>{
    const target=blocks[selectedBlock];if(!target)return;
    target.type=media.kind;target.url=media.url;target.alt=media.alt_text||media.original_name;
    render();commit();library.hidden=true;
  });
  render();
  return {
    setMarkdown(markdown,id="new"){
      documentKey=String(id||"new");clearTimeout(saveTimer);
      textarea.value=text(markdown);blocks=parseCmsMarkdown(textarea.value);render();
      status.textContent="Brouillons synchronisés si la connexion serveur est disponible";
      // Read revision before first save; a parallel tab will cause a conflict
      // instead of silently replacing a more recent draft.
      queueDraftRead(documentKey);
    },
    getMarkdown(){return textarea.hidden?serializeCmsBlocks(blocks):textarea.value;},
    destroy(){clearTimeout(saveTimer);editor.remove();}
  };
}
