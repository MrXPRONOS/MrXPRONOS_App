// Supabase-backed CMS drafts. Each user owns their drafts; RLS rejects other users.
// Optimistic revisions prevent two tabs silently overwriting one another.
export function createServerDraftStore(sb,{kind,getIdentity,onStatus}){
  let revision=null;
  let activeKey=null;
  const identity=()=>String(getIdentity()||"new").slice(0,160);
  const scope=async(identityOverride)=>{
    const {data:{user},error}=await sb.auth.getUser();
    if(error||!user?.id) throw Error("Connexion requise pour enregistrer le brouillon.");
    return {user_id:user.id,kind,identity:String(identityOverride??identity()).slice(0,160)};
  };
  async function read(identityOverride){
    const key=await scope(identityOverride);
    const {data,error}=await sb.from("cms_editor_drafts").select("content,revision,updated_at")
      .eq("user_id",key.user_id).eq("kind",key.kind).eq("identity",key.identity).maybeSingle();
    if(error)throw error;
    activeKey=key.identity;revision=data?.revision??null;
    return data||null;
  }
  async function save(content,identityOverride){
    if(typeof content!=="string" || new TextEncoder().encode(content).length>250000)
      throw Error("Brouillon trop long.");
    const key=await scope(identityOverride);
    if(activeKey!==key.identity){activeKey=key.identity;revision=null;}
    if(revision===null){
      const {data,error}=await sb.from("cms_editor_drafts").insert({...key,content,revision:1})
        .select("revision").single();
      if(error){
        // A second tab may already have created this key. Do not overwrite it.
        if(error.code==="23505")throw Error("Un autre onglet a enregistré un brouillon. Recharge-le avant de modifier.");
        throw error;
      }
      revision=data.revision;
    } else {
      const {data,error}=await sb.from("cms_editor_drafts").update({
        content,revision:revision+1,updated_at:new Date().toISOString()
      }).eq("user_id",key.user_id).eq("kind",key.kind).eq("identity",key.identity)
        .eq("revision",revision).select("revision").maybeSingle();
      if(error)throw error;
      if(!data)throw Error("Brouillon modifié ailleurs : récupère la dernière version avant d'écraser.");
      revision=data.revision;
    }
    onStatus?.("Brouillon synchronisé sur le serveur");
  }
  return {read,save};
}
