// Node.js Neon replacement for Deno ImageScript compositor.
// Keeps EXACT daily banner choice, sizes and fail-open policy of original module.
// Image composition is performed with the same Resvg renderer already used by live.ts.
import { Resvg } from "@resvg/resvg-wasm";
const ART_BASE = "https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/assets/images/";
const ART: Record<string,string> = {
  "1xbet_melbet": "telegram-xpvip-banner.png",
  "1win_betwinner": "telegram-xpvip-banner-1win-betwinner.png"
};
export function liveBannerPack(date = new Date()): string {
  return Math.floor(date.getTime() / 86400000) % 2 === 0 ? "1xbet_melbet" : "1win_betwinner";
}
const bannerCache = new Map<string, Promise<Uint8Array>>();
async function loadBanner(pack: string): Promise<Uint8Array> {
  if (!ART[pack]) throw new Error("Unknown XPVIP banner pack: "+pack);
  let promise=bannerCache.get(pack);
  if (!promise) {
    promise=(async()=>{
      const response=await fetch(ART_BASE+ART[pack]);
      if(!response.ok) throw new Error("XPVIP image HTTP "+response.status);
      return new Uint8Array(await response.arrayBuffer());
    })();
    bannerCache.set(pack,promise);
  }
  try{return await promise;}catch(e){bannerCache.delete(pack);throw e;}
}
function dimensions(png:Uint8Array){
 if(png.length<24 || png[0]!==137 || png[1]!==80 || png[2]!==78 || png[3]!==71)throw Error("Invalid PNG header");
 const view=new DataView(png.buffer,png.byteOffset,png.byteLength);
 const width=view.getUint32(16),height=view.getUint32(20);
 if(width<1||height<1||width>8192||height>8192)throw Error("Invalid PNG size");
 return {width,height};
}
export async function attachLiveSponsorBanner(couponPng: Uint8Array): Promise<Uint8Array> {
 try {
  const pack=liveBannerPack();
  const [coupon,banner]=await Promise.all([Promise.resolve(couponPng),loadBanner(pack)]);
  const cd=dimensions(coupon),bd=dimensions(banner);
  const height=Math.max(1,Math.round(bd.height*cd.width/bd.width));
  if(height>cd.width/3)throw new Error("XPVIP banner aspect ratio invalid");
  const bannerB64=Buffer.from(banner).toString("base64");
  const couponB64=Buffer.from(coupon).toString("base64");
  const svg='<svg xmlns="http://www.w3.org/2000/svg" width="'+cd.width+'" height="'+(height+cd.height)+'" viewBox="0 0 '+cd.width+' '+(height+cd.height)+'">'+
    '<image href="data:image/png;base64,'+bannerB64+'" x="0" y="0" width="'+cd.width+'" height="'+height+'" preserveAspectRatio="none"/>'+
    '<image href="data:image/png;base64,'+couponB64+'" x="0" y="'+height+'" width="'+cd.width+'" height="'+cd.height+'"/>'+
    '</svg>';
  const png=new Resvg(svg,{fitTo:{mode:"original"}}).render().asPng();
  if(png.byteLength<1500)throw Error("Composited PNG invalid");
  return png;
 }catch(error) {
  console.warn("LIVE_BANNER_FALLBACK", String(error));
  return couponPng;
 }
}
