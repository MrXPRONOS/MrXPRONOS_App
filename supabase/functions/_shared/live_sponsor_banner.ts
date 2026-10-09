// Assemble the outgoing LIVE Telegram photo only; do not modify site coupons.
// Reuse the same daily UTC partner alternation as BSD V2.
import { Image } from "https://deno.land/x/imagescript@1.3.0/mod.ts";

const ART_BASE = "https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/assets/images/";
const ART: Record<string, string> = {
  "1xbet_melbet": "telegram-xpvip-banner.png",
  "1win_betwinner": "telegram-xpvip-banner-1win-betwinner.png",
};

export function liveBannerPack(date = new Date()): string {
  return Math.floor(date.getTime() / 86400000) % 2 === 0
    ? "1xbet_melbet"
    : "1win_betwinner";
}

const bannerCache = new Map<string, Promise<Uint8Array>>();
async function loadBanner(pack: string): Promise<Uint8Array> {
  if (!ART[pack]) throw new Error("Unknown XPVIP banner pack: " + pack);
  let promise = bannerCache.get(pack);
  if (!promise) {
    promise = (async () => {
      const response = await fetch(ART_BASE + ART[pack]);
      if (!response.ok) throw new Error("XPVIP image HTTP " + response.status);
      return new Uint8Array(await response.arrayBuffer());
    })();
    bannerCache.set(pack, promise);
  }
  try {
    return await promise;
  } catch (err) {
    bannerCache.delete(pack);
    throw err;
  }
}

export async function attachLiveSponsorBanner(couponPng: Uint8Array): Promise<Uint8Array> {
  try {
    const pack = liveBannerPack();
    const [coupon, banner] = await Promise.all([
      Image.decode(couponPng),
      loadBanner(pack).then(bytes => Image.decode(bytes)),
    ]);
    const height = Math.max(1, Math.round(banner.height * coupon.width / banner.width));
    if (height > coupon.width / 3) throw new Error("XPVIP banner aspect ratio invalid");
    banner.resize(coupon.width, height);
    const output = new Image(coupon.width, height + coupon.height);
    output.composite(banner, 0, 0);
    output.composite(coupon, 0, height);
    return await output.encode();
  } catch (error) {
    // No lost live alerts if a CDN/image processing issue occurs.
    console.warn("LIVE_BANNER_FALLBACK", String(error));
    return couponPng;
  }
}
