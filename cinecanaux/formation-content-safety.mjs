// Strict Formation content recognition and safe outgoing captions.
// No inference by message adjacency, no links copied from third-party posts.
import {classifyFormationPost,courseId} from './formation-private-classifier.mjs';
const URL=/\b(?:https?:\/\/|ftp:\/\/|tg:\/\/|www\.|t\.me\/|telegram\.me\/|(?:[a-z0-9-]+\.)+(?:com|org|net|io|me|fr|tg|co|be|info|biz|xyz|app|link|site|online|store|edu|gov|africa|dev|ly|to|tv|cc|ai|uk|de|ru|ng|ci|sn|bj|cm|gh|us|ca|cloud|tech|live|pro|shop|page|academy|training)\b)[^\s<>"'«»]*/gi;
const HANDLE=/(^|[^\w])@[A-Za-z][A-Za-z0-9_]{1,31}\b/g;
const MARKDOWN=/\[([^\]\n]{1,150})\]\((?:https?:\/\/|tg:\/\/|www\.|t\.me\/)[^)]+\)/gi;
const PROMO=/^\s*(?:[📢🔔✅👉⭐💬🔥\s]*)?(?:likez?|liker|abonn(?:e|ez|ez-vous)|suivez[- ]nous|partagez?|rejoignez[- ]nous|cliquez?|follow|join|subscribe|contactez[- ]nous|code promo|notre canal|nos groupes|voir le lien|lien de t[eé]l[eé]chargement)\b/i;
const LABEL_ONLY=/^(?:lien|link|telegram|contact|whatsapp|rejoignez[- ]nous|abonnez[- ]vous|suivez[- ]nous|canal|channel|site web)\s*[:—-]?\s*$/i;
const norm=s=>String(s||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
 .toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();
const STOP=new Set('tout savoir sur avec les des une dans pour cours course formation formations complete complet guide ultime debutants debutant plus mieux vrai afin sans cela comme votre votrez et le la du au aux de en un une ce cet cette est l d a par partie part fichier fichiers livre ebook formation video videos format niveau tous tout faire apprendre apprendrez tres vous votre maitriser maitrisez francais 2024 2025 2026 2027 1080p 720p zip rar epub pdf docx mp4 mkv part1 part2 part3 vff'.split(' '));
const ext=/\.(?:pdf|mp4|mkv|webm|mov|avi|mp3|m4a|wav|epub|docx|pptx|xlsx|csv|zip|rar|7z|txt|md|srt|vtt)$/i;
const marker=/\b(?:formation|cours complet|masterclass|guide complet|ebook|livre|tutoriel|apprend(?:s|re|ez)?|ma[iî]tris(?:e|er|ez)|formateur|formatrice|🎥|📚|🎓|dur[eé]e|modules?|programme|le[cç]ons?)\b/i;
export function sanitizeFormationText(text,entities=[]){
 let data=String(text||'');
 // Bot API entity offsets are UTF-16 code units, matching JS string slicing.
 const hidden=(entities||[]).filter(e=>['text_link','mention','url'].includes(e?.type))
  .map(e=>[Number(e.offset),Number(e.offset)+Number(e.length)])
  .filter(([a,b])=>Number.isSafeInteger(a)&&Number.isSafeInteger(b)&&
   a>=0&&b>a&&b<=data.length).sort((a,b)=>b[0]-a[0]);
 for(const [a,b] of hidden)data=data.slice(0,a)+data.slice(b);
 data=data.replace(MARKDOWN,'$1')
  .replace(/<a\b[^>]*>(.*?)<\/a>/gi,'$1')
  .replace(URL,'').replace(HANDLE,'$1')
  .replace(/<[^>\n]+>/g,'');
 const lines=data.split(/\r?\n/).map(line=>line.replace(/[ \t]+/g,' ').trim());
 return lines.filter(line=>line&&!PROMO.test(norm(line))&&!LABEL_ONLY.test(line))
  .join('\n').replace(/\n{3,}/g,'\n\n').trim();
}
export function formationHeading(caption){
 const text=sanitizeFormationText(caption);
 const line=/^\s*(?:titre|title)\s*:\s*(.{4,180})\s*$/im.exec(text);
 const value=line?.[1]||text.split(/\r?\n/).find(x=>x.trim())||'';
 return value.replace(/^[^\p{L}\p{N}]+/u,'').trim().slice(0,180);
}
export function inspectFormationCover(caption){
 const text=sanitizeFormationText(caption);
 const id=courseId(text);
 const title=formationHeading(text);
 const raw=String(caption||'');
 if(!title||PROMO.test(norm(title)))return null;
 // Free-form educational fiches require substantive descriptive evidence.
 if(!id && (text.length<48 || text.split('\n').length<2 || !marker.test(raw)))
  return null;
 const explicit=classifyFormationPost(text);
 if(explicit.reason==='explicit_category_invalid_or_conflicting'||
    explicit.reason==='conflicting_course_covers'||
    explicit.reason==='ambiguous_training_domain')return null;
 let category=explicit.category;
 if(!category){
  const fromTitle=classifyFormationPost('Titre: '+title);
  if(fromTitle.reason==='ambiguous_training_domain')return null;
  category=fromTitle.category||'formation_general';
 }
 const authorLine=/^\s*(?:auteur|author|formateur|formatrice|[^\p{L}]*auteur|[^\p{L}]*formateur|[^\p{L}]*formatrice)\s*:\s*([^\n|]{3,100})/imu.exec(text);
 const author=authorLine?.[1]?.trim()||'';
 return {title,caption:text,category,author,course_id:id};
}
function tokens(text){
 return [...new Set(norm(text).replace(/\bpower bi\b/g,'powerbi').split(' ').filter(x=>x.length>=3&&!STOP.has(x)&&!/^\d+$/.test(x)))];
}
export function matchFormationFilename(filename,covers=[]){
 const name=String(filename||'').slice(0,250);
 if(!ext.test(name))return {cover:null,reason:'unsupported_course_file'};
 const fileTokens=tokens(name.replace(ext,'').replace(/\b(?:partie?|volume|vol|chunk|disc|cd)[ _.-]*\d+\b/gi,' '));
 const candidates=[];
 for(const cover of covers||[]){
  const meta=inspectFormationCover(cover?.caption);
  if(!meta)continue;
  const heading=tokens(meta.title);
  const overlap=heading.filter(x=>fileTokens.includes(x));
  if(overlap.length>=2 && overlap.length/Math.max(1,Math.min(fileTokens.length,heading.length))>=0.45 ||
     overlap.length===1 && overlap[0].length>=7 &&
      (heading.length<=2 || fileTokens.length<=2)){
   candidates.push({...meta,message_id:cover.message_id});
  }
 }
 if(candidates.length!==1)return {cover:null,reason:candidates.length?'ambiguous_matching_covers':'no_verified_cover_match'};
 return {cover:candidates[0],reason:'unique_filename_cover'};
}
export function formationFilePart(caption,filename){
 const text=String(caption||'');
 const labeled=/^\s*(?:partie|part|fichier)\s*:\s*([1-9]\d{0,2})\s*\/\s*([1-9]\d{0,2})\s*$/im.exec(text);
 const total=/^\s*(?:total|fichiers)\s*:\s*([1-9]\d{0,2})\s*$/im.exec(text);
 if(labeled){
  const number=Number(labeled[1]),max=Number(labeled[2]);
  return number<=max&&(!total||Number(total[1])===max)?
   {number,total:max,explicit:true}:null;
 }
 if(total)return null;
 const name=String(filename||'');
 const p=/(?:^|[.\s_-])(?:part(?:ie)?|volume|vol|chunk|cd)[\s._-]*0*([1-9]\d{0,2})(?=$|[.\s_-])/i.exec(name);
 return p?{number:Number(p[1]),total:null,explicit:false}:
  {number:1,total:1,explicit:false};
}
export function telegramCaption(text,max=1024){
 const s=sanitizeFormationText(text);
 if(s.length<=max)return s;
 return s.slice(0,max-1).trimEnd()+'…';
}
