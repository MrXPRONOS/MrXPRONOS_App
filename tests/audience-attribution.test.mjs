import test from "node:test";
import assert from "node:assert/strict";
import {classifyLanding,channelOf} from "../assets/js/acquisition-attribution.mjs";

test("known marketing channels are classified but never preserve a full referrer",()=>{
  assert.deepEqual(classifyLanding(
    "https://mrxpronos.github.io/MrXPRONOS_App/pronos.html",
    "https://l.facebook.com/?u=https://example.com/?email=private"),{
    channel:"facebook",campaign:null
  });
  assert.deepEqual(classifyLanding(
    "https://mrxpronos.github.io/MrXPRONOS_App/pronos.html",
    "https://www.google.com/search?q=private+keywords"),{
    channel:"google",campaign:null
  });
  assert.equal(classifyLanding(
    "https://mrxpronos.github.io/MrXPRONOS_App/","https://another-site.example/page?token=secret"
  ).channel,"referral");
});
test("UTM sources and campaign slugs are bounded and normalized",()=>{
  const x=classifyLanding(
    "https://mrxpronos.github.io/MrXPRONOS_App/aujourdhui.html?utm_source=whatsapp&utm_campaign=Pronos-Novembre&utm_medium=social",
    "https://www.google.com/");
  assert.deepEqual(x,{channel:"whatsapp",campaign:"pronos-novembre"});
  const y=classifyLanding(
    "https://mrxpronos.github.io/MrXPRONOS_App/?utm_source=instagram&utm_campaign="+
    encodeURIComponent("COUPON Excel=1")+
    "&access_token=untracked");
  assert.equal(y.channel,"instagram");
  assert.equal(y.campaign,"coupon_excel_1");
  assert.ok(!JSON.stringify(y).includes("access_token"));
  assert.equal(classifyLanding("https://example.com/?utm_campaign="+("a".repeat(300))).campaign?.length,48);
});
test("direct, referral, search and unknown are separate with no fake conversions",()=>{
  assert.equal(classifyLanding("https://example.com/").channel,"direct");
  assert.equal(classifyLanding("https://example.com/","https://example.com/inside").channel,"direct");
  assert.equal(classifyLanding("https://example.com/?utm_source=newservice").channel,"other");
  assert.equal(classifyLanding("https://example.com/","https://bing.com/").channel,"organic_search");
  assert.equal(channelOf("t.me"),"telegram");
  assert.equal(channelOf("youtu.be"),"youtube");
  assert.equal(channelOf("wa.me"),"whatsapp");
  assert.equal(channelOf("pinterest.com"),"pinterest");
  assert.equal(channelOf("linkedin.com"),"linkedin");
});
