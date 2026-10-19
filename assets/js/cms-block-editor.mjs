// A block authoring layer that keeps the existing Markdown CMS field as its source of truth.
import {mountCmsMediaPicker} from "./cms-media-library.mjs";
import {isSafeCmsUrl} from "./cms-url-guard.mjs";
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
  const draftKey=()=>`mx:cms:v2:${kind}:${documentKey}`;
  const commit=()=>{
    textarea.value=serializeCmsBlocks(blocks);
    textarea.dispatchEvent(new Event("input",{bubbles:true}));
    editGeneration+=1;
    status.textContent="Modifications non enregistrées";
    clearTimeout(saveTimer);
    saveTimer=setTimeout(()=>{
      try{
        if(textarea.value.length>150000)return;
        localStorage.setItem(draftKey(),JSON.stringify({at:Date.now(),content:textarea.value}));
        status.textContent="Brouillon local sauvegardé (non publié)";
      }catch {status.textContent="Stockage local indisponible";}
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
  function refreshPreview(){
    preview.replaceChildren(node("h3","Prévisualisation — brouillon local"));
    for(const b of blocks){
      const v=text(b.value);
      if(b.type==="image"&&isSafeCmsUrl(b.url,"image")){
        const img=node("img");img.src=b.url;img.alt=b.alt||"";
        img.style.maxWidth="100%";preview.appendChild(img);
      }else if(b.type==="video"&&isSafeCmsUrl(b.url,"image")){
        const media=node("video");media.controls=true;media.preload="metadata";media.src=b.url;
        media.style.maxWidth="100%";preview.appendChild(media);
      }else if(b.type==="link"&&isSafeCmsUrl(b.url,"link")){
        const a=node("a",v||b.url);a.href=b.url;a.target="_blank";a.rel="noopener noreferrer";preview.appendChild(a);
      }else{
        const tag=b.type==="heading"?"h2":b.type==="subheading"?"h3":b.type==="quote"?"blockquote":"p";
        const element=node(tag,v);element.style.whiteSpace="pre-wrap";preview.appendChild(element);
      }
    }
  }
  add.onclick=()=>{
    blocks.push({type:addType.value,value:"",url:"",alt:""});
    render();list.lastElementChild?.querySelector("textarea,input")?.focus();
  };
  previewBtn.onclick=()=>{preview.hidden=!preview.hidden;if(!preview.hidden)refreshPreview();};
  sourceBtn.onclick=()=>{
    textarea.hidden=!textarea.hidden;
    list.hidden=!textarea.hidden;
    sourceBtn.textContent=textarea.hidden?"Mode source":"Revenir aux blocs";
    if(textarea.hidden){blocks=parseCmsMarkdown(textarea.value);render();}
  };
  recover.onclick=()=>{
    try{
      const draft=JSON.parse(localStorage.getItem(draftKey())||"null");
      if(!draft?.content){status.textContent="Aucun brouillon local";return;}
      if(!window.confirm("Remplacer le texte actuellement saisi par le brouillon local ?"))return;
      textarea.value=draft.content;blocks=parseCmsMarkdown(draft.content);render();status.textContent="Brouillon restauré";
    }catch {status.textContent="Brouillon impossible à relire";}
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
      status.textContent="";
    },
    getMarkdown(){return textarea.hidden?serializeCmsBlocks(blocks):textarea.value;},
    destroy(){clearTimeout(saveTimer);editor.remove();}
  };
}
