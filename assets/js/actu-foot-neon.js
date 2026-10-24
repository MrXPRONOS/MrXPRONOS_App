/**
 * Public Actu Foot snapshot reader on Neon Auth + Data API.
 * Does not share the legacy Supabase client, credentials or release lifecycle.
 */
const NEON_DATA_API_URL="https://ep-wild-hall-b9u7ikuy.apirest.c-7.eu-central-1.aws.neon.tech/mrxpronos/rest/v1";
const NEON_AUTH_URL="https://ep-wild-hall-b9u7ikuy.neonauth.c-7.eu-central-1.aws.neon.tech/mrxpronos/auth";
let clientPromise;

export async function loadNeonFootNews() {
  if(!clientPromise) {
    clientPromise=import("https://esm.sh/@neondatabase/neon-js").then(({createClient})=>
      createClient({auth:{url:NEON_AUTH_URL,allowAnonymous:true},dataApi:{url:NEON_DATA_API_URL}})
    ).catch(error=>{clientPromise=null;throw error});
  }
  const client=await clientPromise;
  const {data,error}=await client.from("actu_foot_news_snapshot")
     .select("payload,generated_at").eq("id","latest").maybeSingle();
  if(error)throw new Error(error.message||"Neon Actu Foot indisponible");
  return Array.isArray(data?.payload)?data.payload:[];
}
