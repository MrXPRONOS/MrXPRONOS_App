export const APP_HTML=String.raw`<!doctype html>
<html lang="fr" data-scene="all">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Ciné Radar — Trouve ton canal</title>
<meta name="theme-color" content="#070f20">
<meta name="description" content="Découvrez les canaux publics Telegram de films, séries et animés.">
<script defer src="https://telegram.org/js/telegram-web-app.js?64"></script>
<style>
:root{color-scheme:dark;--bg:#07101e;--surface:#111e34;--raised:#152640;--border:#2b4166;--muted:#a4b7d5;--blue:#398aff;--violet:#8558fa;--white:#f4f8ff;--heroA:#11295d;--heroB:#1c366b;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--white);background:var(--bg)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;min-height:100vh;min-height:100dvh;background:radial-gradient(ellipse 70% 240px at 67% -120px,#2855a44d,transparent),linear-gradient(180deg,#0a1425 0%,#07101e 52%,#060e1b 100%);-webkit-font-smoothing:antialiased}
button,input{font:inherit}
button{cursor:pointer;-webkit-tap-highlight-color:transparent;touch-action:manipulation}
button:focus-visible,input:focus-visible,.card:focus-visible{outline:2px solid #99b9ff;outline-offset:3px}
button:active{transform:scale(.97)}
.icon{display:inline-flex;align-items:center;justify-content:center;flex:none;width:16px;height:16px}
.icon svg{display:block;width:100%;height:100%;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;fill:none}

/* Lot 2: faithful vector icons from the generated neon 3D SVG set.
   Inline SVG keeps all ten icons sharp without ten image requests. */
.cine-nav-icon{display:inline-block;flex:0 0 22px;width:22px;height:22px;vertical-align:middle;line-height:0;pointer-events:none}
.cine-nav-icon svg{display:block;width:100%;height:100%;overflow:visible}
.cine-drawer-link .cine-nav-icon{width:23px;height:23px;min-width:23px;flex-basis:23px}
.cine-bottom-nav .cine-nav-icon{width:25px;height:25px;flex-basis:25px}
.cine-menu-trigger .cine-nav-icon{width:24px;height:24px}
.cine-drawer-title button .cine-nav-icon{width:23px;height:23px}
.cine-community-share{display:inline-flex;align-items:center;justify-content:center;gap:7px}
.cine-community-share .cine-nav-icon{width:19px;height:19px;flex-basis:19px}
.cine-save{display:flex;align-items:center;justify-content:center;gap:6px}
.cine-save .cine-nav-icon{width:17px;height:17px;flex-basis:17px}
#cine-preview-save{display:inline-flex;align-items:center;justify-content:center;gap:7px}
#cine-preview-save .cine-nav-icon{width:20px;height:20px;flex-basis:20px}
#suggest{display:inline-flex;align-items:center;gap:6px}
#suggest .cine-nav-icon{width:17px;height:17px;flex-basis:17px}
/* Lot 1: ten original glossy cinema icons from a single optimized, transparent WebP sprite. */
.icon.cine-3d-icon{display:inline-block;flex:none;vertical-align:middle;background-image:url('/assets/ui-icons-lot1.webp');background-repeat:no-repeat;background-size:1000% 100%;background-position-y:0}
.cine-icon-sparkle{background-position-x:0%}
.cine-icon-film{background-position-x:11.111111%}
.cine-icon-tv{background-position-x:22.222222%}
.cine-icon-gamepad{background-position-x:33.333333%}
.cine-icon-search{background-position-x:44.444444%}
.cine-icon-eye{background-position-x:55.555556%}
.cine-icon-external{background-position-x:66.666667%}
.cine-icon-back{background-position-x:77.777778%}
.cine-icon-x{background-position-x:88.888889%}
.cine-icon-send{background-position-x:100%}
.page{width:min(100%,1000px);margin:0 auto;padding:18px clamp(12px,3.8vw,28px) calc(32px + env(safe-area-inset-bottom))}
.brand{display:flex;align-items:center;gap:10px;margin:1px 0 19px}
.brand-mark{height:39px;width:39px;border:1px solid #677efa;border-radius:13px;background:linear-gradient(135deg,#172c63,#0c1329 52%,#211a53);display:grid;place-items:center;box-shadow:0 0 24px #456cfc28,inset 0 0 16px #5978ff19;color:#c8dfff}
.brand-mark svg{width:27px;height:27px;filter:drop-shadow(0 2px 4px #7756ff88)}
.brand h1{margin:0;font-size:19px;font-weight:850;letter-spacing:-.65px;line-height:1.08;background:linear-gradient(95deg,#fff 30%,#75a8ff 70%,#ae88ff);-webkit-background-clip:text;background-clip:text;color:transparent}
.brand small{display:block;color:#9aafcc;font-size:10px;letter-spacing:.25px;margin-top:3px}
.hero{position:relative;height:clamp(124px,34vw,193px);border-radius:18px;overflow:hidden;margin-bottom:17px;background:linear-gradient(112deg,#0b1e45,#182f68 50%,#273a6d);border:1px solid #36559699;box-shadow:0 10px 32px #02081374,inset 0 1px #ffffff12;isolation:isolate}
.hero:before{content:"";position:absolute;z-index:1;inset:0;background:linear-gradient(90deg,#081a3ced 0%,#102452c9 35%,#10194630 83%,transparent)}
.hero:after{content:"";position:absolute;inset:0;z-index:0;background:radial-gradient(ellipse at 83% 32%,#488dff60 0%,transparent 40%);opacity:.9}
.hero-art{position:absolute;right:-7px;top:-8px;height:calc(100% + 16px);width:min(75%,520px);z-index:0;opacity:.98;transition:filter .25s}
.hero-art svg{height:100%;width:100%}
.hero-copy{position:relative;z-index:2;padding:clamp(15px,4vw,27px);max-width:69%;height:100%;display:flex;flex-direction:column;justify-content:center;align-items:flex-start}
.hero-copy h2{font-size:clamp(22px,5.4vw,36px);line-height:1.06;font-weight:880;letter-spacing:-1.2px;margin:0 0 8px;text-shadow:0 3px 14px #020a2088}
.hero-copy p{font-size:clamp(10.5px,2.8vw,14px);line-height:1.45;margin:0;color:#deebff;max-width:220px}
.hero-copy .accent{display:block;color:#dbe8ff}
.scene-film,.scene-anime{display:none}
html[data-scene="films"] .scene-default,html[data-scene="series"] .scene-default,html[data-scene="animes"] .scene-default{display:none}
html[data-scene="films"] .scene-film,html[data-scene="series"] .scene-film{display:block}
html[data-scene="animes"] .scene-anime{display:block}
html[data-scene="films"] .hero{background:linear-gradient(110deg,#0c1e40,#233557 55%,#40345b)}
html[data-scene="series"] .hero{background:linear-gradient(110deg,#102142,#25305e 52%,#61345d)}
html[data-scene="animes"] .hero{background:linear-gradient(110deg,#1a2054,#3c3a86 55%,#9e557d)}
html[data-scene="animes"] .hero:after{background:radial-gradient(ellipse at 82% 38%,#e875bf65,transparent 55%)}
.tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-bottom:12px}
.tabs button{min-width:0;height:39px;display:flex;align-items:center;justify-content:center;gap:5px;background:linear-gradient(180deg,#12243c,#0b1a2c);border:1px solid #2d4469;color:#c6d5ef;border-radius:12px;font-size:clamp(10px,2.5vw,12px);font-weight:650;white-space:nowrap;padding:0 2px;transition:background .15s,box-shadow .15s,border-color .15s}
.tabs button .icon{width:13px;height:13px;color:#9cbfff}
.tabs button.active{background:linear-gradient(120deg,#7a50f4,#3e80ff);border-color:#7b99ff;color:#fff;box-shadow:0 5px 15px #4e66f457,inset 0 1px #ffffff56;font-weight:800}
.tabs button.active .icon{color:#fff}
.search{display:flex;align-items:center;gap:10px;height:44px;background:linear-gradient(135deg,#162b48,#12233a);border:1px solid #334c71;border-radius:13px;padding:0 13px;margin-bottom:20px;color:#8cb9fb;box-shadow:inset 0 1px #ffffff0a}
.search .icon{width:19px;height:19px}
.search input{flex:1;min-width:0;background:transparent;border:0;color:#f2f7ff;outline:0;padding:0;font-size:13px}
.search input::placeholder{color:#829aba}
.search-clear{padding:0;border:0;background:#304666;color:#bacef7;border-radius:50%;height:21px;width:21px;display:grid;place-items:center}
.search-clear .icon{width:16px;height:16px}
[hidden]{display:none!important}
.heading{display:flex;justify-content:space-between;align-items:baseline;margin:0 0 12px;gap:10px}
.heading h3{font-size:16px;line-height:1.2;font-weight:800;letter-spacing:-.28px;margin:0}
.heading .count{font-size:11px;color:#a5c3f7;font-variant-numeric:tabular-nums;white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.card{border:1px solid #344e74;background:linear-gradient(160deg,#152741,#0c1c30);border-radius:13px;overflow:hidden;min-width:0;box-shadow:0 5px 14px #0006;transition:transform .15s ease,border-color .15s ease;isolation:isolate}
.card:active{transform:scale(.985)}
.card:hover{border-color:#5285cc}
.card-cover{height:clamp(107px,31vw,178px);position:relative;overflow:hidden;background:linear-gradient(140deg,#182b50,#3b2b6f);display:flex;align-items:center;justify-content:center}
.card-cover:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,transparent 45%,#040b196e);pointer-events:none}
.card-cover img{width:100%;height:100%;object-fit:cover;display:block;position:absolute;inset:0;z-index:2}
.card-cover img.channel-profile-img{width:58%;height:auto;aspect-ratio:1;object-fit:cover;left:50%;top:50%;right:auto;bottom:auto;transform:translate(-50%,-50%);border-radius:50%;border:4px solid rgba(203,221,255,.85);box-shadow:0 9px 28px rgba(0,0,0,.5);z-index:3}
.card-cover:has(img.channel-profile-img){background:radial-gradient(circle at 50% 43%,#4059b3 0%,#152646 70%)}
.card-cover:has(img.channel-profile-img) .cover-illustration{opacity:.18}
.cover-illustration{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.cover-illustration svg{width:100%;height:100%;display:block}
.card[data-type="series"] .card-cover{background:linear-gradient(145deg,#182858,#3f255b)}
.card[data-type="animes"] .card-cover{background:linear-gradient(135deg,#22285a,#81385d)}
.card-body{padding:10px 9px 9px}
.card h4{font-size:clamp(11px,2.8vw,13.2px);font-weight:800;line-height:1.28;letter-spacing:-.18px;margin:0;min-height:31px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}
.card-kind{display:flex;align-items:center;color:#a0b5d6;font-size:10px;margin:3px 0 10px;gap:4px}
.card-actions{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.card-actions button{display:flex;justify-content:center;align-items:center;min-width:0;gap:3px;border-radius:8px;height:31px;border:1px solid transparent;font-size:clamp(10px,2.35vw,12px);font-weight:750;padding:0 2px;white-space:nowrap}
.card-actions .icon{height:16px;width:16px}
.view{background:#233958;color:#e3edff;border-color:#2d4770!important}
.open{background:linear-gradient(120deg,#7156f2,#387ffe);color:white;box-shadow:0 3px 10px #366efc39}
.empty{grid-column:1/-1;border:1px dashed #3d5680;border-radius:16px;background:#101e34;padding:29px 14px;text-align:center;color:#a8bcda;font-size:13px;line-height:1.6}
.empty strong{color:white;display:block;font-size:15px;margin-bottom:6px}
.loading{opacity:.75;animation:pulse 1.6s infinite}
@keyframes pulse{0%,100%{opacity:.65}50%{opacity:1}}
.footer{color:#8298b9;text-align:center;font-size:10px;margin:19px 0 2px;letter-spacing:.12px}
.footer strong{color:#bbcee8;font-weight:650}
.overlay{position:fixed;z-index:40;inset:0;background:#020714d9;display:flex;justify-content:center;align-items:flex-end;backdrop-filter:blur(7px);-webkit-backdrop-filter:blur(7px);padding:0}
.sheet{width:min(100%,540px);height:min(100dvh,870px);max-height:100dvh;position:relative;background:linear-gradient(180deg,#151a32 0%,#101a2c 66%,#071422 100%);display:flex;flex-direction:column;overflow:hidden;box-shadow:0 -12px 60px #000b;border:1px solid #384b73;border-radius:23px 23px 0 0}
.sheet-head{height:51px;flex:none;padding:10px 17px;display:flex;align-items:center;justify-content:space-between;color:#bfd0ef;font-size:12px;font-weight:750;background:#111d31cc}
.sheet-back{display:flex;align-items:center;gap:7px;color:#dbe8ff;background:transparent;border:0;padding:5px 0;font-size:12px}
.sheet-back .icon{width:17px;height:17px}
.sheet-visual{position:relative;flex:0 0 41%;min-height:170px;max-height:350px;overflow:hidden;background:linear-gradient(145deg,#283c81,#674982 60%,#b45e8e);display:grid;place-items:center}
.sheet-visual img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.sheet-visual .cover-illustration{opacity:.94}
.sheet-visual:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,transparent 60%,#151a32 100%);pointer-events:none}
.sheet-detail{position:relative;z-index:1;flex:1;min-height:0;margin-top:-9px;border-radius:23px 23px 0 0;padding:23px 20px max(18px,env(safe-area-inset-bottom));background:linear-gradient(180deg,#181e35,#111b2d);display:flex;flex-direction:column;overflow:auto}
.sheet-profile{display:flex;align-items:center;gap:12px;min-width:0}
.sheet-avatar{width:61px;height:61px;flex:0 0 61px;border-radius:50%;overflow:hidden;background:linear-gradient(140deg,#444db1,#ae61a5);border:2px solid #526ab0;display:grid;place-items:center;color:#dce8ff;box-shadow:0 0 0 4px #182d49}
.sheet-avatar img{width:100%;height:100%;object-fit:cover}
.sheet-name{min-width:0}
.sheet-name h3{margin:0 0 4px;font-size:17px;font-weight:800;letter-spacing:-.4px;line-height:1.2;overflow-wrap:anywhere}
.sheet-name small{color:#a5b7d6;font-size:11px}
.genre-tag{display:inline-flex;margin-top:8px;align-items:center;border-radius:9px;background:#28234e;color:#c0a1ff;padding:5px 10px;font-size:10px;font-weight:700}
.sheet-description{margin:20px 0 15px;font-size:13px;line-height:1.65;color:#d7e0f1;white-space:pre-line;overflow-wrap:anywhere}
.sheet-open{margin-top:auto;flex:none;width:100%;height:49px;border:1px solid #7394ff;border-radius:12px;background:linear-gradient(100deg,#7e50f5 0%,#426ffb 59%,#378cff);box-shadow:0 8px 22px #4b5ffe41;color:#fff;display:flex;align-items:center;justify-content:center;gap:10px;font-size:13px;font-weight:800}
.sheet-open .icon{width:19px;height:19px}
@media(min-width:580px){.page{padding-top:25px}.cards{grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.card-cover{height:165px}.sheet{height:min(90dvh,820px);border-radius:22px}.overlay{align-items:center;padding:20px}.hero{height:195px}}
@media(min-width:850px){.cards{grid-template-columns:repeat(4,minmax(0,1fr))}.card-cover{height:170px}.card-body{padding:12px}.card-actions button{height:34px}.page{padding-top:30px}}
@media(max-width:335px){.tabs button{font-size:10px}.tabs button .icon{width:11px;height:11px}.card-actions button{font-size:9px}.card-actions button .icon{width:11px;height:11px}.hero-copy h2{font-size:21px}}
@media(prefers-reduced-motion:reduce){.loading{animation:none}html{scroll-behavior:auto}.card,.hero-art,.tabs button{transition:none}}

/* V2 — minimal mobile-first controls; descriptions remain in detail sheets. */
.owned-channel-badge{display:inline-flex;width:max-content;align-items:center;padding:3px 8px;border-radius:999px;background:#294d91;color:#e7f3ff;font-size:11px;font-weight:750;margin:5px 0}
.private-channel-label{color:#b0c5df;font-size:11px;margin:4px 0}

.tabs button{height:68px;flex-direction:column;justify-content:center;gap:5px;font-size:clamp(10px,2.6vw,12px);border-radius:14px}
.tabs button .icon{width:23px;height:23px;color:#b7ceff}
.tabs button.active .icon{color:#fff}
.tabs button[data-type="films"]{background:linear-gradient(155deg,#16294e,#243965)}
.tabs button[data-type="series"]{background:linear-gradient(155deg,#1c2650,#34285c)}
.tabs button[data-type="animes"]{background:linear-gradient(155deg,#302854,#4c2a55)}
.tabs button.active{background:linear-gradient(135deg,#7753e4,#366fff)}
@media(max-width:360px){.tabs{gap:4px}.tabs button{height:64px;padding:0 1px;font-size:10px}.tabs button .icon{width:21px;height:21px}}

.v2-tools{display:flex;align-items:center;gap:8px;margin:-9px 0 18px;flex-wrap:wrap}
.v2-tools select,.v2-tools button{background:#162944;border:1px solid #344f78;color:#d7e6ff;border-radius:10px;padding:9px 12px;font-size:12px;font-weight:650;min-height:38px}
.v2-tools button{margin-left:auto}
.tabs button.active{background:linear-gradient(120deg,#6f4df1,#398aff)}
.card-rating{color:#f5c86a;font-weight:750;font-size:11px;min-height:16px;margin-bottom:6px}
.v2-feedback{border-top:1px solid #34476b;margin-top:16px;padding-top:16px;display:flex;flex-direction:column;gap:12px}
.v2-feedback label{display:block;font-size:12px;color:#dae7ff}
.v2-feedback textarea,.v2-feedback select,.v2-feedback input{background:#12243c;border:1px solid #3d5780;color:#f6f9ff;border-radius:9px;font:inherit;padding:10px;width:100%;max-width:100%}
.v2-feedback textarea{min-height:56px;resize:vertical}
.v2-stars{display:flex;gap:7px}
.v2-stars button{border:0;background:#24334c;color:#90a6c8;font-size:24px;border-radius:9px;height:38px;width:40px}
.v2-stars button.selected{color:#ffc85c;background:#3c364d}
.v2-segment{display:flex;gap:5px}
.v2-segment button{flex:1;font-size:11px;border-radius:8px;padding:9px 3px;border:1px solid #3b5379;background:#13253d;color:#dce9ff}
.v2-segment button.selected{background:#3e65ca;color:#fff}
.v2-submit{background:linear-gradient(100deg,#7a4ff0,#387fff);border:0;border-radius:9px;padding:11px;color:white;font-weight:750}
.v2-helper{color:#a3b8d8;font-size:11px;line-height:1.4}
.v2-rating-inline{color:#e5bb66;font-size:11px;font-weight:700}
@media(max-width:390px){.v2-tools{gap:6px}.v2-tools select,.v2-tools button{padding:8px;font-size:11px}}

/* Cine Radar Experience v3: accessible, clean, mobile first */
.hero{height:clamp(145px,32vw,210px);border-color:#49639a;background:linear-gradient(105deg,#07152c,#16294e 57%,#2a245a)!important}
.hero:before{background:linear-gradient(90deg,#07152dfb 0%,#0a1e3cf2 38%,#0a1c3844 85%)!important}
.hero-art{width:62%;right:0;top:0;height:100%;opacity:.95}
.hero-art svg{display:none!important}
.hero-art:before{content:"";position:absolute;inset:-30%;background:repeating-linear-gradient(119deg,transparent 0 33px,#ffffff12 34px 36px,transparent 37px 93px),radial-gradient(ellipse at 60% 40%,#7360ce 0%,transparent 46%),linear-gradient(130deg,#1d3873,#0e183a);transform:rotate(-8deg)}
.hero-art:after{content:"▶";display:grid;place-items:center;position:absolute;right:22%;top:20%;width:74px;height:74px;border-radius:50%;border:9px dotted #ffffff55;box-shadow:0 0 0 12px #334f9a44,0 0 55px #5978ff88;background:#10264bc9;color:white;font-size:27px}
.hero-copy{max-width:74%}
.hero-copy h2{font-size:clamp(22px,5vw,34px)}
.tabs{margin-bottom:12px}
.search{height:50px;margin-bottom:11px;border-color:#5474a5;background:#162c4c}
.search:focus-within{border-color:#8dadff;box-shadow:0 0 0 3px #729bff29}
.search input{font-size:14px}
.cards{gap:13px}
.card{border-radius:16px;border-color:#345077;background:linear-gradient(160deg,#12263f,#0d1b30);box-shadow:0 4px 20px #0005}
.card-cover{height:clamp(92px,26vw,160px);background:linear-gradient(145deg,#193b68,#172346)!important}
.card[data-type="animes"] .card-cover{background:linear-gradient(145deg,#303b74,#462d61)!important}
.card[data-type="series"] .card-cover{background:linear-gradient(145deg,#173d57,#243058)!important}
.card-cover:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 68% 25%,#dbeeff19,transparent 55%),repeating-linear-gradient(90deg,transparent 0 34px,#ffffff08 35px 36px)}
.card-cover .cover-illustration{display:none!important}
.card-cover img.channel-profile-img{width:76px!important;height:76px!important;max-width:58%;border:3px solid #d9e6fcbe;box-shadow:0 8px 22px #0008}
.card-body{padding:12px}
.card h4{font-size:clamp(12px,2.7vw,15px);min-height:35px}
.card-kind{margin:4px 0 6px}
.card-rating{color:#e2bd69}
.card-rating.cine-unrated{color:#96a9c6;font-weight:500}
.card-actions button{height:38px;font-size:clamp(10px,2.4vw,12px)}
.cine-actions{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0 11px}
.cine-actions button,.cine-chips button{cursor:pointer;color:#d9e9ff;background:#152943;border:1px solid #35557e;border-radius:100px;padding:9px 12px;font-size:12px;font-weight:650}
.cine-actions button[aria-pressed="true"],.cine-chips button[aria-pressed="true"]{background:#5048b7;border-color:#919fff;color:white}
.cine-chips{display:flex;gap:7px;overflow-x:auto;scrollbar-width:none;padding:0 0 12px}
.cine-chips button{flex:none;white-space:nowrap}
.cine-feature{margin:12px 0 18px;padding:13px;border-radius:15px;background:#101f36;border:1px solid #324869}
.cine-feature-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px}
.cine-feature-head h3{margin:0 0 4px;font-size:15px}
.cine-feature-head small{color:#99b2d2;font-size:11px}
.cine-feature-items{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}
.cine-feature-item{min-width:0;min-height:83px;display:flex;flex-direction:column;align-items:flex-start;justify-content:space-between;text-align:left;border-radius:10px;border:1px solid #3c547b;background:linear-gradient(140deg,#1c3760,#14243e);padding:10px;color:#f6f9ff}
.cine-feature-item strong{font-size:11px;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.cine-feature-item small{font-size:10px;color:#afc6ea}
.cine-save{margin-top:8px;width:100%;height:30px;background:transparent;border:1px solid #38517b;color:#b8cbec;border-radius:8px;font-size:11px}
.cine-save[aria-pressed="true"]{color:#ffcf74;border-color:#98784c;background:#48392244}
.cine-genre{display:inline-block;font-size:10px;color:#c3dbff;margin:0 0 7px}
.cine-hint{color:#9fbbdf;font-size:11px;margin:0 0 10px}
.cine-empty{padding:23px 14px;border:1px dashed #52719f;border-radius:12px;text-align:center;color:#b4c8e8}
.cine-meta{font-size:12px;color:#b6c9e9;background:#142943;padding:12px;border:1px solid #304f79;border-radius:10px;line-height:1.8}
.cine-meta strong{color:#f7fbff}
@media(min-width:700px){.cine-feature-items{grid-template-columns:repeat(3,1fr)}.card-cover img.channel-profile-img{width:98px!important;height:98px!important}.cards{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:350px){.cine-feature-items{grid-template-columns:1fr 1fr}.cine-feature-item:last-child{display:none}.cine-actions button{padding:8px}}
@media(prefers-reduced-motion:reduce){.card,.hero-art{transition:none!important}}


/* Ciné Radar V4 — navigation claire et pages distinctes */
body{background:#07111f}
.page{max-width:980px;padding-bottom:calc(94px + env(safe-area-inset-bottom))}
.brand{position:relative;margin-bottom:16px;min-height:48px;padding-right:52px}
.cine-menu-trigger{position:absolute;right:0;top:1px;width:43px;height:43px;display:grid;place-items:center;border:1px solid #35527b;border-radius:13px;background:#142945;color:#e6efff;font-size:24px}
.cine-menu-trigger[aria-expanded=true]{border-color:#8c92fa;background:#2b3469}
.cine-panel[hidden],.cine-drawer-backdrop[hidden],.cine-private-empty[hidden]{display:none!important}
.cine-panel{animation:cine-enter .16s ease-out}
@keyframes cine-enter{from{opacity:.7;transform:translateY(4px)}to{opacity:1;transform:none}}
.cine-head{margin:4px 0 18px}
.cine-head h2{font-size:clamp(21px,5vw,27px);margin:0 0 6px;line-height:1.18;letter-spacing:-.5px}
.cine-head p{color:#9eb4d1;margin:0;font-size:13px;line-height:1.5}
.cine-hero{margin-bottom:17px;height:clamp(149px,33vw,195px)}
.cine-hero .hero-copy{max-width:76%}
.cine-hero .hero-copy h2{font-size:clamp(23px,5vw,33px);letter-spacing:-.8px}
.cine-hero .hero-copy p{font-size:clamp(11px,2.7vw,14px)}
.cine-hero .hero-art:before{background:radial-gradient(ellipse at 68% 29%,#9a7ce34d,transparent 47%),linear-gradient(120deg,#253d73,#17224b)}
.cine-hero .hero-art:after{display:none}
.cine-hero{background:#0b1a35}
.cine-hero .hero-art{width:min(85%,630px);opacity:.96;right:-12%;overflow:hidden}
.cine-hero .hero-art>svg{opacity:.17}
.cine-hero:before{background:linear-gradient(90deg,#091932 0%,#091b36ed 35%,#101d43ad 57%,#0a183a35 100%);z-index:1}
.cine-hero-collage{position:absolute;inset:-6px -14px;overflow:hidden;pointer-events:none;z-index:1;mask-image:linear-gradient(90deg,transparent,#000 21%,#000 88%,transparent)}
.cine-marquee-track{height:100%;display:flex;align-items:center;gap:9px;width:max-content;animation:cine-scroll-hero 39s linear infinite;will-change:transform}
.cine-hero-cover{position:relative;flex:0 0 89px;height:133px;border-radius:10px;overflow:hidden;transform:rotate(-5deg);border:1px solid #a3baf399;box-shadow:0 8px 20px #000a;background:linear-gradient(140deg,#1b3266,#613a81)}
.cine-hero-cover:nth-child(3n){transform:rotate(6deg) translateY(-5px)}
.cine-hero-cover:nth-child(5n){transform:rotate(-8deg) translateY(7px)}
.cine-hero-cover img,.cine-film-poster img{width:100%;height:100%;object-fit:cover;display:block}
.cine-hero-cover span{position:absolute;inset:auto 3px 5px;color:#fff;font-size:10px;font-weight:800;text-align:center;text-shadow:0 2px 5px #000}
.cine-poster-section{margin:1px 0 19px}
.cine-poster-section-title{display:flex;justify-content:space-between;align-items:center;margin:0 0 9px;gap:8px}
.cine-poster-section-title strong{font-size:15px;letter-spacing:.1px}
.cine-poster-section-title small{font-size:10px;color:#9ab5db}
.cine-poster-window{position:relative;overflow:hidden;mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent);border-radius:12px}
.cine-poster-track{display:flex;gap:10px;width:max-content;animation:cine-scroll-posters 70s linear infinite;will-change:transform}
.cine-film-poster{width:99px;height:144px;flex:0 0 99px;position:relative;border-radius:11px;overflow:hidden;border:1px solid #405b86;background:linear-gradient(155deg,#243b78,#9e477e 67%,#1c2449);margin:0;box-shadow:0 5px 18px #0006}
.cine-film-poster:nth-child(4n){background:linear-gradient(155deg,#22476e,#a17a54,#2c3e67)}
.cine-film-poster figcaption{position:absolute;bottom:0;left:0;right:0;padding:15px 6px 6px;font-size:10px;font-weight:760;color:#fff;line-height:1.1;background:linear-gradient(transparent,#030614df);text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cine-film-poster .cine-poster-placeholder{position:absolute;inset:0;display:grid;place-items:center;font-size:26px;color:#dbe7ff7a;font-weight:900;letter-spacing:2px}
.cine-poster-note{margin:8px 0 0;font-size:10px;color:#91a8c9}
@keyframes cine-scroll-hero{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@keyframes cine-scroll-posters{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.cine-hero:hover .cine-marquee-track,.cine-poster-window:hover .cine-poster-track{animation-play-state:paused}
@media (prefers-reduced-motion:reduce){.cine-marquee-track,.cine-poster-track{animation:none!important}}
@media (max-width:400px){.cine-hero-cover{flex-basis:72px;height:111px}.cine-film-poster{flex-basis:87px;width:87px;height:132px}}

.cine-hero-cover:nth-child(3){left:74%;top:24%;transform:rotate(14deg)}
.cine-home-search{display:flex;align-items:center;gap:9px;background:#172d4b;border:1px solid #43618c;border-radius:14px;padding:7px 8px 7px 15px;margin:0 0 18px;height:54px}
.cine-home-search input{min-width:0;flex:1;color:#f5f9ff;background:transparent;border:0;outline:0;font-size:13px}
.cine-home-search input::placeholder{color:#91a9c9}
.cine-home-search button,.cine-primary{border:0;background:linear-gradient(115deg,#7157e9,#367cf5);color:white;border-radius:10px;padding:10px 14px;font-weight:750;font-size:12px}
.cine-section-title{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin:14px 0 11px}
.cine-section-title h3{font-size:17px;margin:0}
.cine-link{border:0;background:transparent;color:#a8c9ff;font-size:12px;padding:5px}
.cine-quick{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:3px 0 22px}
.cine-quick button{background:#13253e;border:1px solid #334d70;color:#eaf2ff;border-radius:13px;padding:14px 9px;min-height:78px;display:flex;flex-direction:column;align-items:flex-start;justify-content:space-between;text-align:left;gap:8px;font-size:12px;font-weight:750}
.cine-quick span{font-size:22px}
.cine-home-picks,.cine-discover-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
.cine-pick{min-width:0;background:linear-gradient(165deg,#1a3151,#102035);border:1px solid #324c74;color:#f5f9ff;border-radius:13px;padding:12px 9px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:9px;min-height:156px}
.cine-home-picks{grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}
.cine-home-picks .cine-pick{min-height:177px;border-color:#486b9f}
.cine-home-picks .cine-pick:nth-child(-n+2){min-height:205px;background:linear-gradient(160deg,#284773,#152440 72%);border-color:#6588d0;box-shadow:0 9px 24px #06112870}
.cine-home-picks .cine-pick:nth-child(-n+2) .cine-pick-avatar{width:82px;height:82px;border-radius:21px}
.cine-pick-stat{font-size:10px;color:#8ed6fc;line-height:1.2}
@media(min-width:690px){.cine-home-picks{grid-template-columns:repeat(3,minmax(0,1fr))}}
.cine-pick-avatar{width:65px;height:65px;border-radius:18px;background:#293d6a;display:grid;place-items:center;overflow:hidden;border:1px solid #6b83b6;color:#e1eeff;font-size:22px}
.cine-pick-avatar img{width:100%;height:100%;object-fit:cover}
.cine-pick strong{font-size:11px;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}
.cine-pick small{color:#afc5e0;font-size:10px}
.cine-home-footer{margin:15px 0 0;color:#9cb2d0;font-size:12px}
.cine-explore-options{margin:8px 0 16px;background:#101f33;border:1px solid #284267;border-radius:12px;padding:9px 12px}
.cine-explore-options summary{cursor:pointer;color:#c7daff;font-size:12px;font-weight:750;list-style:none}
.cine-explore-options summary:after{content:"⌄";float:right}
.cine-explore-options[open] summary:after{content:"⌃"}
.cine-explore-options nav.tabs{margin:15px 0}
.cine-explore-options .v2-tools{margin:0;display:flex;gap:10px;align-items:center}
.cine-explore-options .v2-tools button{display:none}
.cine-explore-options .v2-tools select{margin:0}
.cine-genre-chips{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;margin-bottom:13px;padding:4px 0}
.cine-genre-chips button,.cine-genre-tile{flex:none;border:1px solid #3b5476;background:#152942;color:#dce9ff;border-radius:50px;padding:10px 13px;font-size:12px}
.cine-genre-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:15px 0 24px}
.cine-genre-tile{border-radius:15px;text-align:left;min-height:92px;display:flex;flex-direction:column;justify-content:space-between;gap:8px}
.cine-genre-tile b{font-size:14px;color:#fff}
.cine-genre-tile small{color:#a7c1e2}
.cine-note{font-size:12px;color:#b6c9e4;line-height:1.65;background:#112238;border:1px solid #2b4468;border-radius:12px;padding:13px;margin:16px 0}
.cine-note button{margin-top:8px}
.cine-private-empty{text-align:center;padding:28px 14px;border-radius:12px;border:1px dashed #486287;background:#111e32;color:#adc3e3;font-size:13px;line-height:1.6}
.cine-save{margin-top:8px;width:100%;height:35px;background:#172c46;border:1px solid #365579;color:#b5cdec;border-radius:8px;font-size:11px}
.cine-save[aria-pressed=true]{color:#ffd176;border-color:#a18354;background:#51412140}
.cine-rating-empty{color:#8da7c7!important}
.card-cover .cover-illustration{display:none!important}
.card-cover{background:linear-gradient(120deg,#192f58,#342c66)!important}
.card-cover:before{background:radial-gradient(circle at 70% 20%,#b3ccff22,transparent 60%),linear-gradient(160deg,#182f55,#2f315b)}
.card-cover:has(img.channel-profile-img) .cover-illustration{display:none!important}
.card-body{padding:11px}
.card h4{min-height:33px}
.cine-stats{color:#92b0d7;font-size:11px}
.cine-helper{margin:16px 0;padding:14px;border-radius:13px;background:#102035;border:1px solid #314e71;color:#d3e2fa;font-size:13px;line-height:1.6}
.cine-helper h3{font-size:15px;margin:0 0 7px;color:#f6f9ff}
.cine-helper p{margin:7px 0}
.cine-helper button,.cine-soft-button{background:#18375d;border:1px solid #5573a0;color:#e8f1ff;border-radius:10px;padding:11px 13px;font-size:12px;font-weight:700}
.cine-drawer-backdrop{position:fixed;inset:0;z-index:110;background:#020914bd;display:flex;justify-content:flex-end}
.cine-drawer{width:min(88vw,340px);height:100%;overflow:auto;background:#0c1a2d;border-left:1px solid #3b587f;padding:23px 20px calc(36px + env(safe-area-inset-bottom));box-shadow:-15px 0 40px #0009}
.cine-drawer-title{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:22px}
.cine-drawer-title b{font-size:21px}
.cine-drawer-title button{background:#19324f;color:#fff;border:1px solid #45658f;border-radius:10px;width:39px;height:39px;font-size:23px}
.cine-drawer-subtitle{color:#819abb;text-transform:uppercase;letter-spacing:1.2px;font-size:10px;margin:19px 0 8px}
.cine-drawer-link{width:100%;display:flex;align-items:center;gap:12px;text-align:left;border:0;border-radius:11px;color:#e9f2ff;background:transparent;padding:13px 11px;font-size:14px}
.cine-drawer-link span{min-width:22px;text-align:center;font-size:18px}
.cine-drawer-link[aria-current=page]{background:#243d69}
.cine-drawer-foot{font-size:11px;color:#94abc9;margin:22px 0}
.cine-bottom-nav{position:fixed;z-index:85;bottom:0;left:0;right:0;display:grid;grid-template-columns:repeat(4,1fr);background:#0b1b30f5;border-top:1px solid #36537b;backdrop-filter:blur(14px);padding:8px max(8px,env(safe-area-inset-left)) calc(8px + env(safe-area-inset-bottom))}
.cine-bottom-nav button{border:0;background:transparent;color:#9fb6d7;display:flex;flex-direction:column;align-items:center;gap:4px;min-height:43px;font-size:10px;font-weight:680}
.cine-bottom-nav button span{font-size:20px}
.cine-bottom-nav button[aria-current=page]{color:#f2f7ff}
.cine-bottom-nav button[aria-current=page] span{color:#8aa7ff}
.cine-hint-warning{font-size:12px;color:#ffdca5}
.cine-info-data{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:12px}
.cine-info-data div{border:1px solid #385176;border-radius:10px;padding:13px;background:#162942}
.cine-info-data strong{font-size:19px;display:block}
.cine-info-data small{font-size:11px;color:#9fb9db}
.cine-empty-spot{font-size:12px;color:#a7bedb}
@media(min-width:720px){.cine-bottom-nav{max-width:570px;margin:auto;border:1px solid #3b547e;border-bottom:0;border-radius:15px 15px 0 0}.cine-pick{min-height:176px}.cine-hero-cover{width:96px;height:136px}.cine-hero-cover:nth-child(1){left:38%}}
@media(max-width:350px){.cine-home-picks{grid-template-columns:repeat(2,minmax(0,1fr))}.cine-home-picks .cine-pick:last-child{display:none}.cine-quick{gap:6px}.cine-genre-grid{gap:7px}}
@media(prefers-reduced-motion:reduce){.cine-panel{animation:none}}


/* Verified titles linked to real messages from the three primary channels. */
.radar-available{margin:18px 0 26px}
.radar-available h3{font-size:1.05rem;margin:0 0 6px}
.radar-available p{font-size:.8rem;color:#b2bdd5;margin:0 0 12px}
.radar-available-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(126px,1fr));gap:11px}
.radar-title-card{appearance:none;cursor:pointer;border:1px solid #34456e;border-radius:13px;padding:7px;background:#111e38;color:#fff;text-align:left;display:flex;flex-direction:column;gap:5px;min-width:0;transition:border-color .15s,transform .15s}
.radar-title-card:hover,.radar-title-card:focus-visible{border-color:#90afff;transform:translateY(-2px)}
.radar-title-poster{aspect-ratio:2/3;width:100%;border-radius:9px;object-fit:cover;background:#172647;display:block}
.radar-title-card strong{font-size:.82rem;line-height:1.3;overflow-wrap:anywhere}
.radar-title-card small{font-size:.72rem;color:#bbcbeb}
.radar-status{border:1px dashed #485c84;border-radius:12px;padding:16px;color:#b8c6df;background:#0e1b36;font-size:.84rem}
.radar-primary-links{display:flex;gap:8px;flex-wrap:wrap;margin:9px 0 14px}
.radar-primary-links a{border-radius:20px;border:1px solid #40547c;padding:6px 9px;color:#d7e2ff;text-decoration:none;font-size:.79rem}

/* Compact, one-row home navigation; pinned images are tap targets. */
.cine-home-search{height:46px;margin:0 0 10px;padding:5px 7px 5px 13px}
.cine-home-search button{padding:8px 12px}
.cine-poster-section{margin:0 0 13px}
.cine-poster-section-title{margin-bottom:7px}
.cine-section-title{margin:10px 0 9px}
.cine-quick{grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:2px 0 13px}
.cine-quick button{min-height:42px;flex-direction:row;align-items:center;justify-content:center;gap:7px;padding:8px 7px;text-align:center;border-radius:10px;font-size:12px;white-space:nowrap}
.cine-quick button span{font-size:17px;line-height:1}
.cine-quick button .cine-3d-icon{width:23px;height:23px}
.cine-quick button strong{font-size:12px}
.cine-poster-track.cine-poster-short{animation:none;min-width:100%}
.cine-film-poster{appearance:none;padding:0;text-align:left;cursor:pointer;color:#fff;touch-action:manipulation}
.cine-film-poster:focus-visible{outline:2px solid #a1b9ff;outline-offset:3px}
.cine-film-poster .cine-pin-label{position:absolute;bottom:0;left:0;right:0;padding:15px 6px 7px;background:linear-gradient(transparent,#020715ed);font-size:10px;font-weight:790;line-height:1.15;z-index:3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cine-pin-kind{position:absolute;top:5px;left:5px;padding:3px 6px;background:#071529d9;color:#eef6ff;z-index:4;border-radius:6px;font-size:9px}
.cine-pins-empty{min-height:46px;width:100%;border-radius:10px;border:1px dashed #394f78;background:#101e35;display:flex;align-items:center;justify-content:center;text-align:center;padding:10px;font-size:12px;color:#adbfdb}

/* Discrete editorial cross-promotion, placed after initial home discoveries. */
.cine-promo-slot{grid-column:1/-1;min-width:0;margin:2px 0 8px;border:1px solid #34496b;border-radius:14px;background:linear-gradient(135deg,#102139,#0c1b30);padding:11px}
.cine-promo-head{display:flex;justify-content:space-between;gap:6px;align-items:baseline;margin:0 1px 9px}
.cine-promo-head strong{font-size:13px;letter-spacing:-.1px}
.cine-promo-head small{color:#8ba2c2;font-size:9px;white-space:nowrap}
.cine-promo-track{display:flex;gap:8px;min-width:0;width:100%;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;scroll-snap-type:none;padding-bottom:3px;overscroll-behavior-inline:contain}
.cine-promo-track::-webkit-scrollbar{display:none}
.cine-promo-card{position:relative;flex:0 0 clamp(220px,76%,360px);min-width:0;min-height:91px;display:flex;align-items:center;gap:9px;text-decoration:none;color:#eaf2ff;border:1px solid #3a5377;background:#152a44;border-radius:11px;padding:10px;transition:border-color .15s,background .15s}
.cine-promo-card:hover,.cine-promo-card:focus-visible{border-color:#84aafa;background:#1b3657;outline-offset:2px}
.cine-promo-avatar{position:relative;flex:0 0 43px;height:43px;border-radius:50%;overflow:hidden;display:grid;place-items:center;background:#243f69;border:1px solid #6883b0;font-size:21px}
.cine-promo-avatar img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.cine-promo-copy{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.cine-promo-name{font-size:11.5px;line-height:1.2;overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
.cine-promo-description{color:#b2c7e4;font-size:10px;line-height:1.3;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;line-clamp:2;overflow:hidden}
.cine-promo-age{font-size:9px;color:#f1c993;line-height:1.2}
.cine-promo-arrow{flex:none;align-self:flex-start;color:#9db8e3;font-size:14px}
@media(min-width:690px){.cine-promo-slot{margin:4px 0 9px}}
@media(max-width:350px){.cine-promo-card{flex-basis:220px}.cine-promo-slot{padding:9px}.cine-promo-head small{font-size:8px}}

/* Discovery cards retain the original responsive grid; only the separate promotion track scrolls. */
.cine-community{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:12px 0;color:#a6bce0}
.cine-community-share{background:#273f78;color:#eaf4ff;border:1px solid #5876b0;border-radius:10px;padding:9px 12px;font-size:12px;font-weight:750}
.cine-community small{font-size:10px}
.cine-community-rating{display:flex;flex-wrap:wrap;align-items:center;gap:7px;background:#112b45;border:1px solid #3b5c89;border-radius:11px;padding:10px;margin:7px 0 15px;font-size:12px}
.cine-rating-buttons{display:flex;gap:4px}
.cine-rating-buttons button{background:#263d66;border:1px solid #47658d;color:#ffe1a6;border-radius:7px;padding:5px 7px;font-size:11px}
.cine-rate-later{background:transparent;border:0;color:#aac8f2;text-decoration:underline;padding:5px;font-size:11px}
@media(prefers-reduced-motion:reduce){.cine-home-picks{scroll-behavior:auto}}

/* Lot 3: ten original transparent cinematic category illustrations, packed in one
   compact 560x56 WebP (56px per cell) to avoid multiple network requests. */
.cine-cat-icon{display:inline-block;flex:0 0 auto;width:34px;height:34px;vertical-align:middle;background-image:url('/assets/ui-icons-lot3.webp');background-repeat:no-repeat;background-size:1000% 100%;background-position-y:0;pointer-events:none}
.cine-cat-films{background-position-x:0%}
.cine-cat-series{background-position-x:11.111111%}
.cine-cat-animes{background-position-x:22.222222%}
.cine-cat-action{background-position-x:33.333333%}
.cine-cat-romance{background-position-x:44.444444%}
.cine-cat-africain{background-position-x:55.555556%}
.cine-cat-vostfr{background-position-x:66.666667%}
.cine-cat-turc{background-position-x:77.777778%}
.cine-cat-drame{background-position-x:88.888889%}
.cine-cat-affiches{background-position-x:100%}
.cine-genre-tile .cine-genre-label{display:flex;align-items:center;min-width:0;gap:9px}
.cine-genre-tile .cine-genre-label strong{color:#f5f9ff;font-size:13px;line-height:1.2;overflow-wrap:anywhere}
.cine-genre-tile .cine-cat-icon{width:45px;height:45px}
.cine-genre-chips button{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.cine-genre-chips button .cine-cat-icon{width:22px;height:22px}
.cine-poster-section-title strong{display:inline-flex;align-items:center;gap:7px}
.cine-poster-section-title strong .cine-cat-icon{width:29px;height:29px}
.cine-film-poster .cine-poster-placeholder .cine-cat-icon{width:46px;height:46px}
.cine-hero-cover .cine-poster-placeholder{position:absolute;inset:0;display:grid;place-items:center}
.cine-hero-cover .cine-poster-placeholder .cine-cat-icon{width:54px;height:54px}
.cine-pin-kind{display:inline-flex;align-items:center;gap:3px}
.cine-pin-kind .cine-cat-icon{width:13px;height:13px}
@media(max-width:350px){.cine-genre-tile{padding:9px}.cine-genre-tile .cine-cat-icon{width:37px;height:37px}.cine-genre-tile .cine-genre-label{gap:5px}.cine-genre-tile .cine-genre-label strong{font-size:12px}}
</style>
</head>
<body>
<main class="page">
<header class="brand">
 <div class="brand-mark" aria-hidden="true"><svg viewBox="0 0 40 40" fill="none"><defs><linearGradient id="logo-grad" x1="0" x2="1" y1="1" y2="0"><stop stop-color="#925bff"/><stop offset=".5" stop-color="#407cff"/><stop offset="1" stop-color="#b7e9ff"/></linearGradient></defs><circle cx="19" cy="18" r="12" stroke="url(#logo-grad)" stroke-width="4"/><circle cx="15" cy="14" r="2.4" fill="#eff8ff"/><circle cx="24" cy="14" r="2.4" fill="#eff8ff"/><circle cx="19" cy="22" r="2.4" fill="#eff8ff"/><path d="M4 30c8 5 24 5 32-6M29 10l6 4-1-8" stroke="url(#logo-grad)" stroke-width="3.6" stroke-linecap="round"/></svg></div>
 <div><h1>Ciné Radar</h1><small>Les canaux cinéma au même endroit.</small></div>
</header>
<section class="hero" aria-label="Présentation de Ciné Radar">
 <div class="hero-art" aria-hidden="true">
  <svg viewBox="0 0 460 228" preserveAspectRatio="xMidYMid slice">
   <defs><linearGradient id="scene-sky" x1="0" y1="0" x2=".9" y2="1"><stop stop-color="#163c91"/><stop offset=".5" stop-color="#476bc7"/><stop offset=".79" stop-color="#bd72af"/><stop offset="1" stop-color="#fcb98e"/></linearGradient><radialGradient id="scene-glow"><stop stop-color="#b8d8ff" stop-opacity=".96"/><stop offset=".34" stop-color="#80aaff" stop-opacity=".7"/><stop offset="1" stop-color="#3761ff" stop-opacity="0"/></radialGradient><linearGradient id="scene-ground" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#1a3c73"/><stop offset="1" stop-color="#07172e"/></linearGradient><filter id="scene-blur"><feGaussianBlur stdDeviation="6"/></filter></defs>
   <rect width="460" height="228" fill="url(#scene-sky)"/>
   <circle cx="310" cy="75" r="112" fill="url(#scene-glow)"/>
   <g fill="#fff" opacity=".5"><circle cx="237" cy="21" r="1.4"/><circle cx="387" cy="34" r="1.2"/><circle cx="432" cy="100" r="1.6"/><circle cx="276" cy="116" r="1"/></g>
   <path d="M0 151 41 135 69 147 108 118 140 130 172 111 219 124 255 103 284 112 332 94 383 128 420 111 460 120V228H0Z" fill="#1c3061" opacity=".45"/>
   <path d="M0 174 33 160 33 136 53 136 53 158 69 158 69 140 98 140 98 154 129 147 129 124 145 124 145 149 169 140 169 116 181 116 181 139 217 146 217 128 239 128 239 147 264 147 264 119 292 119 292 140 320 138 320 125 340 125 340 146 384 149 384 117 398 117 398 153 430 153 430 143 460 143V228H0Z" fill="#101c40" opacity=".93"/>
   <g fill="#9dc5ff" opacity=".3"><path d="M141 134h3v5h-3zM151 134h3v5h-3zM272 127h4v6h-4zM282 127h4v6h-4zM386 122h4v5h-4zM386 132h4v5h-4zM79 147h3v4h-3zM90 147h3v4h-3z"/></g>
   <path d="M0 189Q170 172 460 189V228H0Z" fill="url(#scene-ground)"/>
   <g class="scene-default">
   <g transform="translate(330 116)"><ellipse cx="6" cy="107" rx="75" ry="11" fill="#030819" opacity=".48" filter="url(#scene-blur)"/><path d="M-29 90c-14-32 5-51 37-50 42 2 53 29 45 55l-17 24h-52z" fill="#091a34"/><ellipse cx="9" cy="20" rx="18" ry="22" fill="#07182f"/><path d="M-10 17C-10-5 24-12 32 16l-19-5-20 13z" fill="#08192e"/><path d="M-29 77Q-60 77-69 65" stroke="#081729" stroke-width="14" fill="none" stroke-linecap="round"/></g>
   <g transform="translate(353 38) rotate(-18)"><circle r="34" fill="#55aaff" opacity=".93" stroke="#b6dbff" stroke-width="3"/><path d="m-11-14 29 16-29 16z" fill="#f5f9ff"/><path d="M-37 6Q0-1 31-30" fill="none" stroke="#d0e7ff" stroke-width="3" opacity=".4"/></g>
   </g>
   <g class="scene-film">
    <path d="M280 0h76L230 220h-88Z" fill="#ffe9cd" opacity=".17"/>
    <circle cx="321" cy="35" r="31" fill="#ffdab0" opacity=".27"/>
    <path d="M380 83 417 58 444 75 413 99Z" fill="#a5b9e8" stroke="#d5e5ff" stroke-width="3"/>
    <path d="M398 85 366 186M421 86l28 100M403 94v97" stroke="#0a1430" stroke-width="6"/>
    <rect x="267" y="101" width="91" height="58" rx="8" fill="#0d1b3c" stroke="#a9cdff" stroke-width="4"/>
    <circle cx="296" cy="98" r="27" fill="#163968" stroke="#b3d2ff" stroke-width="3"/>
    <circle cx="333" cy="91" r="24" fill="#163968" stroke="#b3d2ff" stroke-width="3"/>
    <g fill="#b4d8fa"><circle cx="289" cy="87" r="6"/><circle cx="305" cy="102" r="6"/><circle cx="335" cy="81" r="6"/><circle cx="347" cy="96" r="5"/></g>
    <path d="m273 131-28-17v35z" fill="#8cc4fa"/>
    <path d="m283 159-32 61m88-61 29 61m-56-61v61" stroke="#09172f" stroke-width="9"/>
    <g fill="#0a142c"><path d="M205 149h63v10h-63zM211 160h9v40h-9zM258 160h9v40h-9z"/><path d="m197 202 25-10h46l24 10z"/></g>
   </g>
   <g class="scene-anime">
    <circle cx="351" cy="66" r="42" fill="#ffc5bc" opacity=".87"/>
    <path d="M210 151 256 113 292 142 331 105 379 143 418 121 460 149v80H210Z" fill="#5d468a" opacity=".87"/>
    <path d="M195 164q61-17 129 2t136-10v72H195z" fill="#162b58" opacity=".88"/>
    <path d="M250 181q70-16 155 0M260 194q62-10 142 0" stroke="#ffb6c6" opacity=".56" stroke-width="3" fill="none"/>
    <path d="M380 58v115M440 58v115M355 59h111M365 68l-11 37h18M450 68l12 37h-18" stroke="#172047" stroke-width="10" fill="none" stroke-linecap="round"/>
    <path d="M359 63h103" stroke="#ffa3b9" stroke-width="4"/>
    <g fill="#ffd2df" opacity=".85"><circle cx="275" cy="38" r="3"/><circle cx="304" cy="14" r="3"/><circle cx="436" cy="28" r="3"/><circle cx="241" cy="76" r="4"/></g>
   </g>
  </svg>
 </div>
 <div class="hero-copy"><h2>Un clic,<span class="accent">un canal.</span></h2><p>Films, séries et animés au même endroit.</p></div>
</section>
<nav class="tabs" aria-label="Catégories" id="tabs">
 <button type="button" data-type="all" class="active" aria-pressed="true"><span class="icon" data-icon="sparkle"></span>Tous</button>
 <button type="button" data-type="films" aria-pressed="false"><span class="icon" data-icon="film"></span>Films</button>
 <button type="button" data-type="series" aria-pressed="false"><span class="icon" data-icon="tv"></span>Séries</button>
 <button type="button" data-type="animes" aria-pressed="false"><span class="icon" data-icon="gamepad"></span>Animés</button>
</nav>
<label class="search" for="search"><span class="icon" data-icon="search"></span><input id="search" type="search" autocomplete="off" placeholder="Rechercher un canal…" aria-label="Rechercher un canal"><button class="search-clear" type="button" id="searchClear" aria-label="Effacer la recherche" hidden><span class="icon" data-icon="x"></span></button></label>
<div class="v2-tools"><select id="sort" aria-label="Trier les canaux"><option value="relevant">Pertinents</option><option value="rated">Mieux notés</option><option value="recent">Récents</option><option value="new">Nouveaux</option></select><button type="button" id="suggest">＋ Proposer un canal</button></div>
<div class="heading"><h3 id="heading">Les canaux</h3><span class="count" id="count">—</span></div>
<section class="cards" id="cards" aria-live="polite"><div class="empty loading">Chargement des canaux…</div></section>
<footer class="footer"><strong>Ciné Radar</strong> · Annuaire public</footer>
</main>
<div class="overlay" id="overlay" role="dialog" aria-modal="true" aria-label="Aperçu du canal" hidden>
 <div class="sheet" id="sheet"></div>
</div>
<script>
(function(){
const PRELOADED_CATALOG=null;
window.__CINERADAR_INITIAL_CATALOG__=PRELOADED_CATALOG;
const telegram=()=>window.Telegram?.WebApp||null;
document.addEventListener("DOMContentLoaded",()=>{try{telegram()?.ready();telegram()?.expand();}catch{}});
const $=id=>document.getElementById(id);
const validLink=url=>/^https:\/\/t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?$/.test(String(url||""))||/^https:\/\/t\.me\/(?:\+[A-Za-z0-9_-]{12,}|joinchat\/[A-Za-z0-9_-]{12,})\/?$/.test(String(url||""));
const photoHost=url=>/^\/assets\/channel-avatar\/(?:[a-z][a-z0-9_]{4,31}|[1-9][0-9]{0,9})\.jpg$/i.test(String(url||""))||/^https:\/\/(?:[a-z0-9-]+\.)*(?:telesco\.pe|telegram\.org|telegram-cdn\.org|t\.me)\/[^\s"'<>]{1,1200}$/i.test(String(url||""));
const icons={
 sparkle:'<path d="m12 2 1.6 6.4L20 10l-6.4 1.6L12 18l-1.6-6.4L4 10l6.4-1.6L12 2Z"/><path d="m19 18 .5 1.5L21 20l-1.5.5L19 22l-.5-1.5L17 20l1.5-.5L19 18Z"/>',
 film:'<rect x="3" y="5" width="18" height="15" rx="2"/><path d="M3 10h18M7 5l3 5M14 5l3 5M7 14h10"/>',
 tv:'<rect x="3" y="6" width="18" height="13" rx="2"/><path d="m8 3 4 3 4-3M8 22h8"/>',
 gamepad:'<path d="M6 9h12a4 4 0 0 1 3.9 3l1 6a2.5 2.5 0 0 1-4 2.2L15 17H9l-3.9 3.2A2.5 2.5 0 0 1 1 18l1-6a4 4 0 0 1 4-3Z"/><path d="M7 12v6M4 15h6M17 14h.1M20 16h.1"/>',
 search:'<circle cx="11" cy="11" r="7.5"/><path d="m16.7 16.7 4.2 4.2"/>',
 eye:'<path d="M2 12s3.7-6.2 10-6.2S22 12 22 12s-3.7 6.2-10 6.2S2 12 2 12Z"/><circle cx="12" cy="12" r="2.9"/>',
 external:'<path d="M13 5h6v6M19 5l-9 9"/><path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"/>',
 back:'<path d="m15 18-6-6 6-6"/>',
 x:'<path d="M5 5 19 19M19 5 5 19"/>',
 send:'<path d="m21 3-8.5 18-2.5-7-7-2.5L21 3Z"/><path d="M10 14 21 3"/>',
 clapper:'<rect x="3" y="8" width="18" height="13" rx="2"/><path d="M3 8V4l17-2 1 6M7 3l4 5M14 2l4 6"/>'
};
const lot1Icons=new Set(["sparkle","film","tv","gamepad","search","eye","external","back","x","send"]);
function ico(key){
 const holder=document.createElement("span");holder.className="icon";holder.setAttribute("aria-hidden","true");
 if(lot1Icons.has(key))holder.classList.add("cine-3d-icon","cine-icon-"+key);
 else holder.innerHTML='<svg viewBox="0 0 24 24">'+(icons[key]||icons.film)+'</svg>';
 return holder;
}
document.querySelectorAll("[data-icon]").forEach(x=>x.replaceWith(ico(x.dataset.icon)));
let type="all",query="",channels=[],allChannels=[],lastFetch=0,fetchPending=null,images=new Map(),inFlight=new Map(),previewToken=0,thumbQueue=[],thumbActive=0;
const selectedTypes=new Set();let searchDelay=null;
const MAX_THUMB_FETCH=2;
function showChannelImage(img,source,backup,exhausted){
 const isLocalAvatar=/^\/assets\/channel-avatar\/[1-9][0-9]{0,9}\.jpg$/.test(String(source||""));
 const candidates=isLocalAvatar?[source+"?v=3",source+"?v=3&refresh=1"]:[source];
 if(backup&&photoHost(backup)&&backup!==source)candidates.push(backup);
 let current=0;
 img.onerror=()=>{current++;if(current<candidates.length)img.src=candidates[current];else if(exhausted)exhausted()};
 img.src=candidates[0];
}
const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
function button(text,cls,callback,icon){
 const b=node("button",cls);b.type="button";
 if(icon)b.append(ico(icon));
 b.append(document.createTextNode(text));
 b.onclick=e=>{e.stopPropagation();callback();};return b;
}
async function api(path){
 const c=new AbortController(),timeout=setTimeout(()=>c.abort(),10000);
 try{const r=await fetch(path,{cache:"default",signal:c.signal});const body=await r.json();if(!r.ok)throw Error(body.error||"Service indisponible");return body;}
 finally{clearTimeout(timeout);}
}
function openTelegram(link){if(!validLink(link))return;const app=telegram();if(app?.openTelegramLink)app.openTelegramLink(link);else window.open(link,"_blank","noopener");}
function typeLabel(t){return t==="animes"?"Animés":t==="series"?"Séries":"Films";}
function sceneSVG(t,index=0){
 const anime=t==="animes",series=t==="series";
 const sky=anime?["#373d88","#d67da1"]:series?["#26385f","#8c4066"]:["#152f62","#415cc0"];
 const id="art-"+t+"-"+index;
 // Decorative scenery only; not a fabricated film poster or channel photo.
 const scenery=anime?
 '<circle cx="175" cy="55" r="30" fill="#ffbdad" opacity=".8"/><path d="M0 132 48 94 77 120 124 91 170 125 217 80 240 112V160H0Z" fill="#29376e"/><path d="M0 139h240v21H0Z" fill="#0c2041"/><path d="M52 78h6v61h-6zM30 79h49v6H30zM38 85l-8 20h12zM68 85l11 20H67z" fill="#122b51"/><path d="M0 151q55-26 120-6t120-4" stroke="#f59ecb" stroke-width="3" fill="none" opacity=".65"/>' :
 series?
 '<path d="M0 122 240 105v55H0z" fill="#0b152e"/><rect x="59" y="28" width="125" height="89" rx="7" fill="#0b1c3b" stroke="#93adfc" stroke-width="3"/><rect x="69" y="38" width="105" height="68" rx="3" fill="#4b3380"/><path d="M69 94c25-45 45-34 63-61l42 0v73H69z" fill="#8559a9" opacity=".8"/><circle cx="137" cy="65" r="17" fill="#ffc4c7" opacity=".72"/><path d="M100 117v9m43-9v9m-44 0h45" stroke="#a5c1ff" stroke-width="4"/>' :
 '<path d="M0 139 240 121v39H0z" fill="#07182d"/><path d="M0 134 65 112 96 131 151 100 190 126 240 103v57H0Z" fill="#142959"/><circle cx="142" cy="61" r="45" fill="#9dc5ff" opacity=".25"/><path d="M64 83h102l-15 16H77z" fill="#9cbcf8"/><circle cx="111" cy="54" r="38" fill="#1c3c76" stroke="#cce6ff" stroke-width="3"/><circle cx="111" cy="54" r="10" fill="#aacfff"/><circle cx="89" cy="36" r="6" fill="#a8cfff"/><circle cx="131" cy="36" r="6" fill="#a8cfff"/><circle cx="89" cy="74" r="6" fill="#a8cfff"/><circle cx="131" cy="74" r="6" fill="#a8cfff"/><path d="M111 90v38m-24 0h49" stroke="#aacfff" stroke-width="6"/>';
 return '<svg viewBox="0 0 240 160" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs><linearGradient id="'+id+'" x1="0" y1="0" x2="1" y2="1"><stop stop-color="'+sky[0]+'"/><stop offset="1" stop-color="'+sky[1]+'"/></linearGradient></defs><rect width="240" height="160" fill="url(#'+id+')"/><circle cx="192" cy="28" r="76" fill="#add6ff" opacity=".12"/>'+scenery+'</svg>';
}
function close(){previewToken++;$("overlay").hidden=true;$("sheet").textContent="";document.body.style.overflow="";}
function makeArt(t,id){const art=node("div","cover-illustration");art.innerHTML=sceneSVG(t,id);return art;}
function buildCard(c,i){
 const card=node("article","card");card.dataset.channelId=String(c.id);card.dataset.type=c.type;
 const cover=node("div","card-cover");cover.append(makeArt(c.type,c.id));
 const directAvatar=photoHost(c.avatar)?c.avatar:photoHost(c.photo)?c.photo:null;
 if(directAvatar){const img=node("img",photoHost(c.avatar)?"channel-profile-img":null);img.alt="Photo de profil du canal "+c.title;img.loading="lazy";img.decoding="async";showChannelImage(img,directAvatar,c.photo,()=>img.remove());cover.append(img);}
 const body=node("div","card-body");body.append(node("h4",null,c.title));
 if(c.featured)body.append(node("div","owned-channel-badge","✦ À la une"));
 if(c.private_channel)body.append(node("div","private-channel-label","🔒 Canal privé"));
 body.append(node("div","card-kind",typeLabel(c.type)));
 if(c.review_count){body.append(node("div","card-rating","★ "+Number(c.rating).toFixed(1)+" · "+c.review_count+" avis"));}else{body.append(node("div","card-rating","Pas encore noté"));}
 const actions=node("div","card-actions");
 actions.append(button("Aperçu","view",()=>showPreview(c),"eye"),button("Ouvrir","open",()=>openTelegram(c.link),"external"));
 body.append(actions);card.append(cover,body);
 card.setAttribute("aria-label",c.title);
 return card;
}
function render(){
 const root=$("cards");root.textContent="";
 $("count").textContent=channels.length+" cana"+(channels.length===1?"l":"ux");
 $("heading").textContent=query.trim()?"Résultats de recherche":"Les canaux";
 if(!channels.length){
  const empty=node("div","empty");empty.append(node("strong",null,"Aucun canal trouvé"),document.createTextNode("Essaie une autre recherche ou une autre catégorie."));
  const suggestions=document.createElement("div");suggestions.className="cine-no-results";suggestions.style.marginTop="14px";for(const [word,term] of [["Films","films"],["Séries","series"],["Animés","animes"]]){const b=document.createElement("button");b.type="button";b.textContent=word;b.style.cssText="margin:4px;padding:9px 13px;border-radius:100px;background:#24416a;color:#f1f7ff;border:1px solid #5071a2";b.onclick=()=>{const search=$("search");search.value=term;search.dispatchEvent(new Event("input",{bubbles:true}));};suggestions.append(b);}empty.append(suggestions);root.append(empty);return;
 }
 const fragment=document.createDocumentFragment();
 channels.forEach((c,i)=>fragment.append(buildCard(c,i)));
 root.append(fragment);
}
function updatePreviewThumb(id,p){
 images.set(id,p);
 const source=allChannels.find(x=>x.id===id);
 if(!source)return;
 const url=[source.avatar,p.photo,p.post_image].find(photoHost);
 if(!url)return;
 source.photo=url;
 const cover=Array.from($("cards").children).find(x=>Number(x.dataset.channelId)===id)?.querySelector(".card-cover");
 if(cover&&!cover.querySelector("img")){
  const img=node("img",url===source.avatar?"channel-profile-img":null);img.alt="Photo du canal "+source.title;img.loading="lazy";img.decoding="async";showChannelImage(img,url,null,()=>img.remove());cover.append(img);
 }
}
async function getPreview(id){
 if(images.has(id))return images.get(id);
 if(inFlight.has(id))return inFlight.get(id);
 const pending=api("/api/channel-preview?id="+encodeURIComponent(id)).then(r=>r.channel).then(p=>{updatePreviewThumb(id,p);return p;}).finally(()=>inFlight.delete(id));
 inFlight.set(id,pending);return pending;
}
function pumpThumbs(){
 while(thumbActive<MAX_THUMB_FETCH&&thumbQueue.length){
  const id=thumbQueue.shift();
  if(images.has(id)||inFlight.has(id))continue;
  thumbActive++;
  getPreview(id).catch(()=>{}).finally(()=>{thumbActive--;pumpThumbs();});
 }
}
function enqueueVisiblePhotos(){
 for(const c of channels.slice(0,4)){
  if(!photoHost(c.photo)&&!images.has(c.id)&&!inFlight.has(c.id)&&!thumbQueue.includes(c.id))thumbQueue.push(c.id);
 }
 pumpThumbs();
}
function applyFilters(){
 channels=allChannels.filter(c=>!selectedTypes.size||[...selectedTypes].some(t=>c.type===t||String(c.tags||"").split(",").includes(t)));
 render();enqueueVisiblePhotos();
}
async function load(force=false){
 if(fetchPending)return fetchPending;
 if(!force&&allChannels.length&&Date.now()-lastFetch<120000){applyFilters();return;}
 const requested=query+'|'+Array.from(selectedTypes).sort().join(',')+'|'+$("sort").value;
 const url="/api/search?q="+encodeURIComponent(query)+"&types="+encodeURIComponent(Array.from(selectedTypes).join(','))+"&sort="+encodeURIComponent($("sort").value)+"&limit=80";
 if(!allChannels.length){$("count").textContent="…";$("cards").textContent="";$("cards").append(node("div","empty loading","Recherche en cours…"));}
 fetchPending=(async()=>{
  try{const result=await api(url);if(result&&Array.isArray(result.channels)){allChannels=result.channels;lastFetch=Date.now();applyFilters();}}
  catch{if(!allChannels.length){$("cards").textContent="";$("cards").append(node("div","empty","Connexion momentanément indisponible."));}}
  finally{fetchPending=null;const current=query+'|'+Array.from(selectedTypes).sort().join(',')+'|'+$("sort").value;if(current!==requested)load(true);}
 })();
 return fetchPending;
}

async function postV2(path,data){
 const init=telegram()?.initData||"";
 if(!init)throw Error("Ouvre Ciné Radar depuis Telegram pour participer.");
 const response=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json","X-Telegram-Init-Data":init},body:JSON.stringify(data)});
 let result;try{result=await response.json();}catch{result={};}
 if(!response.ok)throw Error(result.error||"Envoi impossible. Réessaie.");
 return result;
}
function statusLine(parent,message){
 let existing=parent.querySelector(".v2-result");
 if(!existing){existing=node("div","v2-helper v2-result");existing.setAttribute("role","status");parent.append(existing);}
 existing.textContent=message;
}
function createFeedback(c){
 const area=node("section","v2-feedback");
 const heading=node("strong",null,"Ton avis");area.append(heading);
 const help=node("div","v2-helper","As-tu trouvé ce que tu cherchais ?");
 area.append(help);
 const stars=node("div","v2-stars");let rating=0;
 for(let n=1;n<=5;n++){
  const b=button("★",null,()=>{rating=n;for(const item of stars.children)item.classList.toggle("selected",Number(item.dataset.rate)<=n);});
  b.dataset.rate=String(n);b.setAttribute("aria-label",n+" étoiles");stars.append(b);
 }area.append(stars);
 const row=node("div","v2-segment");let accuracy="yes";
 for(const [key,label] of [["yes","Oui"],["part","En partie"],["no","Non"]]){
  const b=button(label,key==="yes"?"selected":"",()=>{accuracy=key;for(const other of row.children)other.classList.toggle("selected",other.dataset.match===key);});
  b.dataset.match=key;row.append(b);
 }
 area.append(row);
 const comment=node("textarea");comment.maxLength=500;comment.placeholder="Commentaire (facultatif)";comment.setAttribute("aria-label","Commentaire");area.append(comment);
 area.append(button("Publier mon avis","v2-submit",async()=>{
  if(!rating){statusLine(area,"Choisis de 1 à 5 étoiles.");return;}
  try{await postV2("/api/channels/"+c.id+"/reviews",{rating,matches_description:accuracy,comment:comment.value});statusLine(area,"Avis enregistré. Merci !");load(true);}
  catch(e){statusLine(area,String(e.message||e));}
 }));
 const flag=node("select");flag.setAttribute("aria-label","Motif du signalement");
 for(const [key,label] of [["","Signaler un problème…"],["wrong_category","Mauvaise catégorie"],["misleading","Description trompeuse"],["dead_link","Lien inutilisable"],["spam","Spam"],["copyright","Contenu non autorisé"],["other","Autre"]]){const o=node("option");o.value=key;o.textContent=label;flag.append(o);}
 area.append(flag);
 area.append(button("Envoyer le signalement","v2-submit",async()=>{
  if(!flag.value){statusLine(area,"Choisis un motif.");return;}
  try{await postV2("/api/reports",{channel_id:c.id,reason:flag.value});statusLine(area,"Signalement reçu.");}
  catch(e){statusLine(area,String(e.message||e));}
 }));
 const comments=node("div","v2-helper");comments.textContent="Avis de la communauté";area.append(comments);
 api("/api/channels/"+c.id+"/reviews").then(data=>{
  if(!area.isConnected)return;
  const count=data.summary?.count||0;comments.textContent=count?count+" avis · "+Number(data.summary.rating).toFixed(1)+"/5":"Aucun avis pour le moment";
  for(const item of (data.reviews||[]).slice(0,3)){
   const el=node("div","v2-helper","★ "+item.rating+" · "+item.comment);area.append(el);
  }
 }).catch(()=>{});
 return area;
}
function showSuggestion(){
 previewToken++;$("overlay").hidden=false;document.body.style.overflow="hidden";
 const sheet=$("sheet");sheet.textContent="";
 const head=node("div","sheet-head");
 head.append(button("Retour","sheet-back",close,"back"),node("span",null,"Proposer un canal"));sheet.append(head);
 const detail=node("div","sheet-detail");detail.append(node("h3",null,"Ajouter un canal"));
 const area=node("section","v2-feedback");
 const link=node("input");link.type="url";link.placeholder="https://t.me/nomducanal";link.setAttribute("aria-label","Lien Telegram public");area.append(link);
 const kind=node("select");kind.setAttribute("aria-label","Catégorie du canal");
 for(const [key,label] of [["films","Films"],["series","Séries"],["animes","Animés"]]){const o=node("option");o.value=key;o.textContent=label;kind.append(o);}area.append(kind);
 area.append(button("Proposer","v2-submit",async()=>{
  try{const reply=await postV2("/api/suggestions",{link:link.value.trim(),category:kind.value});statusLine(area,reply.status==="already_listed"?"Ce canal figure déjà dans Ciné Radar.":"Merci ! Ta proposition a bien été envoyée.");}
  catch(e){statusLine(area,String(e.message||e));}
 }));
 area.append(node("div","v2-helper","Seuls les liens des canaux publics sont référencés."));detail.append(area);sheet.append(detail);
}

function fillPreview(c,p){
 const sheet=$("sheet");sheet.textContent="";
 const bar=node("div","sheet-head");const back=button("Retour","sheet-back",close,"back");
 bar.append(back,node("span",null,"Ciné Radar · Aperçu"));sheet.append(bar);
 const visual=node("div","sheet-visual");visual.append(makeArt(c.type,"preview-"+c.id));
 const url=[p?.post_image,p?.photo,c.avatar,c.photo].find(photoHost);
 if(url){const img=node("img");img.alt="Image publique du canal "+c.title;img.decoding="async";img.onerror=()=>img.remove();img.src=url;visual.append(img);}
 sheet.append(visual);
 const detail=node("div","sheet-detail");
 const profile=node("div","sheet-profile");
 const avatar=node("div","sheet-avatar");avatar.append(ico(c.type==="series"?"tv":c.type==="animes"?"gamepad":"film"));
 const profilePhoto=[c.avatar,p?.photo,c.photo].find(photoHost);
 if(profilePhoto){avatar.textContent="";const img=node("img");img.alt="Photo de profil du canal";showChannelImage(img,profilePhoto,p?.photo,()=>{avatar.textContent="";avatar.append(ico("film"));});avatar.append(img);}
 const names=node("div","sheet-name");names.append(node("h3",null,p?.title||c.title),node("small",null,c.private_channel?"Canal privé Telegram":"Canal Telegram"));
 const tag=node("div","genre-tag",typeLabel(c.type));names.append(tag);profile.append(avatar,names);detail.append(profile);
 const usefulBio=p?.description&&!p.description.startsWith("Canal Telegram public")?p.description:
  "Découvre ce canal de "+typeLabel(c.type).toLowerCase()+" sur Telegram.";
 detail.append(node("p","sheet-description",usefulBio));
 detail.append(button("Ouvrir le canal","sheet-open",()=>openTelegram(c.link),"send"));
 detail.append(createFeedback(c));
 sheet.append(detail);
}
document.addEventListener("cineradar:show-preview",event=>{
 const c=event.detail?.channel,id=Number(event.detail?.id);
 if(!Number.isSafeInteger(id)||id<1||!c||Number(c.id)!==id||!validLink(c.link))return;
 showPreview(c);
});
function showPreview(c){
 const token=++previewToken;
 $("overlay").hidden=false;document.body.style.overflow="hidden";
 fillPreview(c,images.get(c.id));
 if(images.has(c.id))return;
 getPreview(c.id).then(p=>{if(token===previewToken&&!$("overlay").hidden)fillPreview(c,p);}).catch(()=>{});
}
for(const b of document.querySelectorAll("[data-type]"))b.onclick=()=>{
 const chosen=b.dataset.type;
 if(chosen==="all"){selectedTypes.clear();type="all";}
 else{if(selectedTypes.has(chosen))selectedTypes.delete(chosen);else selectedTypes.add(chosen);type=selectedTypes.size===1?Array.from(selectedTypes)[0]:"all";}
 document.documentElement.dataset.scene=type;
 for(const x of document.querySelectorAll("[data-type]")){const active=x.dataset.type==="all"?!selectedTypes.size:selectedTypes.has(x.dataset.type);x.classList.toggle("active",active);x.setAttribute("aria-pressed",String(active));}
 applyFilters();load(true);
};
$("search").oninput=e=>{
 query=e.target.value.slice(0,120);$("searchClear").hidden=!query.length;
 clearTimeout(searchDelay);searchDelay=setTimeout(()=>load(true),230);
};
$("searchClear").onclick=()=>{$("search").value="";query="";$("searchClear").hidden=true;load(true);$("search").focus();};
$("sort").onchange=()=>load(true);
$("suggest").onclick=showSuggestion;
document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible"&&Date.now()-lastFetch>120000)load(true);});
$("overlay").onclick=e=>{if(e.target===$("overlay"))close();};
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!$("overlay").hidden)close();});
if(Array.isArray(PRELOADED_CATALOG)&&PRELOADED_CATALOG.length){
 allChannels=PRELOADED_CATALOG;lastFetch=Date.now();applyFilters();
}
load();
})();
</script>
<script>

(function(){
"use strict";
const $=id=>document.getElementById(id);
const node=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el};
const cineCategoryKeys=new Set(["films","series","animes","action","romance","africain","vostfr","turc","drame","affiches"]);
function cineCategoryIcon(key){
 const icon=node("span","cine-cat-icon cine-cat-"+(cineCategoryKeys.has(key)?key:"films"));
 icon.setAttribute("aria-hidden","true");
 return icon;
}

/* Ten original 3D navigation icon drawings, ported from the approved SVG files.
   The source art remains editable as vector paths, not baked into emoji/font glyphs. */
const cineNavGeometry={
 accueil:[["s","M116 255 L256 129 L396 255",42],["s","M161 253 V383 H351 V253",42],["f","M226 389 V308 Q226 294 240 294 H272 Q286 294 286 308 V389 Z",7]],
 explorer:[["s","M395 250 A139 139 0 1 1 117 250 A139 139 0 1 1 395 250",35],["f","M316 183 L278 285 L188 330 L230 219 Z",8],["dot","256","257","11"]],
 decouvrir:[["f","M249 100 C260 153 282 195 333 218 C281 229 260 270 249 351 C233 271 217 231 165 218 C219 199 235 154 249 100 Z",9],["f","M366 302 Q374 331 400 340 Q373 348 366 378 Q361 350 335 340 Q359 331 366 302 Z",4],["f","M123 100 Q130 126 153 136 Q130 145 123 169 Q118 144 95 136 Q117 127 123 100 Z",4]],
 favoris:[["s","M256 114 L301 202 L404 216 L329 287 L348 386 L256 339 L164 386 L183 287 L108 216 L211 202 Z",34]],
 historique:[["s","M139 190 C177 102 298 91 363 156 C435 229 390 353 308 390 C230 426 151 391 118 325",31],["s","M110 194 L143 190 L152 225",31],["s","M257 176 V258 L322 298",34]],
 proposer:[["s","M169 124 H343 Q387 124 387 168 V344 Q387 388 343 388 H169 Q125 388 125 344 V168 Q125 124 169 124 Z",33],["s","M256 183 V327 M184 255 H328",47]],
 apropos:[["s","M404 256 A148 148 0 1 1 108 256 A148 148 0 1 1 404 256",34],["s","M256 255 V331",39],["f","M234 179 a22 22 0 1 0 44 0 a22 22 0 1 0 -44 0",9]],
 menu:[["s","M119 162 H393",45],["s","M119 256 H393",45],["s","M119 350 H393",45]],
 fermer:[["s","M149 148 L363 364 M363 148 L149 364",57]],
 partager:[["s","M153 361 L362 152 M257 152 H362 V257",48],["s","M332 347 H168 Q133 347 133 312 V201",27]]
};
let cineNavCounter=0;
function cineNavIcon(key){
 const parts=cineNavGeometry[key];
 if(!parts)throw Error("Unknown navigation icon: "+key);
 const prefix="cine-nav-"+(++cineNavCounter)+"-";
 const url=name=>"url(#"+prefix+name+")";
 const defs='<defs>'+
  '<linearGradient id="'+prefix+'neon" x1="95" y1="95" x2="420" y2="420" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#B1F9FF"/><stop offset=".18" stop-color="#00D6FF"/><stop offset=".46" stop-color="#1D8DF8"/><stop offset=".76" stop-color="#6343EC"/><stop offset="1" stop-color="#B331FF"/></linearGradient>'+
  '<linearGradient id="'+prefix+'glass" x1="135" y1="95" x2="405" y2="420" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#F6FFFF" stop-opacity=".47"/><stop offset=".38" stop-color="#5FDDFE" stop-opacity=".03"/><stop offset=".82" stop-color="#771AFF" stop-opacity=".11"/><stop offset="1" stop-color="#180A88" stop-opacity=".27"/></linearGradient>'+
  '<linearGradient id="'+prefix+'shine" x1="90" y1="90" x2="405" y2="405" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#F4FFFF"/><stop offset=".45" stop-color="#90F2FF" stop-opacity=".55"/><stop offset="1" stop-color="#CD90FF" stop-opacity=".06"/></linearGradient>'+
  '<linearGradient id="'+prefix+'edge" x1="90" y1="90" x2="418" y2="418" gradientUnits="userSpaceOnUse"><stop stop-color="#C8FFFF"/><stop offset=".48" stop-color="#39A8FA"/><stop offset="1" stop-color="#8734EE"/></linearGradient>'+
  '</defs>';
 const art=parts.map(part=>{
  if(part[0]==="dot")return '<circle cx="'+part[1]+'" cy="'+part[2]+'" r="'+part[3]+'" fill="#D9F8FF" stroke="#76DDFF" stroke-width="4"/>';
  const d=part[1],w=part[2];
  if(part[0]==="f")return '<path d="'+d+'" transform="translate(0 13)" fill="#111052" stroke="#090B37" stroke-width="'+(w+9)+'" stroke-linejoin="round" opacity=".85"/>'+
    '<path d="'+d+'" fill="'+url("neon")+'" stroke="#1D4AAB" stroke-width="'+(w+5)+'" stroke-linejoin="round"/>'+
    '<path d="'+d+'" fill="'+url("glass")+'" stroke="'+url("edge")+'" stroke-width="'+w+'" stroke-linejoin="round"/>';
  return '<path d="'+d+'" transform="translate(1 13)" fill="none" stroke="#0B0C42" stroke-width="'+(w+16)+'" stroke-linecap="round" stroke-linejoin="round" opacity=".8"/>'+
    '<path d="'+d+'" fill="none" stroke="#142B8B" stroke-width="'+(w+12)+'" stroke-linecap="round" stroke-linejoin="round"/>'+
    '<path d="'+d+'" fill="none" stroke="'+url("neon")+'" stroke-width="'+w+'" stroke-linecap="round" stroke-linejoin="round"/>'+
    '<path d="'+d+'" fill="none" stroke="'+url("shine")+'" stroke-width="'+(w*.23).toFixed(1)+'" stroke-linecap="round" stroke-linejoin="round" transform="translate(-5 -5)" opacity=".75"/>';
 }).join("");
 const holder=node("span","cine-nav-icon");
 holder.dataset.cineNavIcon=key;
 holder.setAttribute("aria-hidden","true");
 holder.innerHTML='<svg viewBox="0 0 512 512" focusable="false">'+defs+art+'</svg>';
 return holder;
}
function favoriteLabel(target,selected,preview=false){
 target.replaceChildren(cineNavIcon("favoris"),document.createTextNode(selected?(preview?"Retirer des favoris":"Dans mes favoris"):"Ajouter aux favoris"));
 target.setAttribute("aria-pressed",String(selected));
}
const saveKey="cine-radar-favorites-v3",historyKey="cine-radar-history-v3";
const validChannelLink=url=>/^https:\/\/t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?$/.test(String(url||""))||/^https:\/\/t\.me\/(?:\+[A-Za-z0-9_-]{12,}|joinchat\/[A-Za-z0-9_-]{12,})\/?$/.test(String(url||""));
const photoHost=url=>/^\/assets\/channel-avatar\/(?:[a-z][a-z0-9_]{4,31}|[1-9][0-9]{0,9})\.jpg$/i.test(String(url||""))||/^https:\/\/(?:[a-z0-9-]+\.)*(?:telesco\.pe|telegram\.org|telegram-cdn\.org|t\.me)\/[^\s"\x27<>]{1,1200}$/i.test(String(url||""));
const read=(key,max)=>{try{const v=JSON.parse(localStorage.getItem(key)||"[]");return Array.isArray(v)?v.map(Number).filter(x=>Number.isSafeInteger(x)&&x>0).slice(0,max):[]}catch{return []}};
let favorites=read(saveKey,250),recent=read(historyKey,60),catalog=[],mode="explorer",currentPreview=null,drawerOpen=false;
const pages=["accueil","explorer","decouvrir","favoris","historique","proposer","apropos"];
const labels={accueil:"Accueil",explorer:"Explorer",decouvrir:"Découvrir",favoris:"Favoris",historique:"Historique",proposer:"Proposer un canal",apropos:"À propos"};
let panel={},listing,existing,oldFocus=null;
function persist(){try{localStorage.setItem(saveKey,JSON.stringify(favorites));localStorage.setItem(historyKey,JSON.stringify(recent))}catch{}}
function showChannelImage(img,source,backup,exhausted){
 const isLocalAvatar=/^\/assets\/channel-avatar\/[1-9][0-9]{0,9}\.jpg$/.test(String(source||""));
 const candidates=isLocalAvatar?[source+"?v=3",source+"?v=3&refresh=1"]:[source];
 if(backup&&photoHost(backup)&&backup!==source)candidates.push(backup);
 let current=0;
 img.onerror=()=>{current++;if(current<candidates.length)img.src=candidates[current];else if(exhausted)exhausted()};
 img.src=candidates[0];
}
function linkAvatar(c){const src=String(c.avatar||"");return /^\/assets\/channel-avatar\/([1-9][0-9]{0,9}|[a-z][a-z0-9_]{4,31})\.jpg$/i.test(src)?src:(Number.isSafeInteger(Number(c.id))&&Number(c.id)>0?"/assets/channel-avatar/"+c.id+".jpg":null)}
function setHash(page){const h="#/"+page;if(location.hash!==h)location.hash=h;else navigate(page)}
function switchPanel(p){pages.forEach(n=>{panel[n].hidden=n!==p});document.querySelectorAll("[data-go]").forEach(b=>{if(b.dataset.go===p)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current")});document.title=(p==="accueil"?"Ciné Radar":labels[p]+" | Ciné Radar");window.scrollTo({top:0,behavior:"instant"})}
function makeNav(label,page,icon){const b=node("button",null);b.type="button";b.dataset.go=page;b.append(cineNavIcon(icon),document.createTextNode(label));b.onclick=()=>{closeMenu();setHash(page)};return b}
function openMenu(){const b=$("cine-menu-backdrop");if(!b)return;oldFocus=document.activeElement;b.hidden=false;drawerOpen=true;$("cine-menu-trigger").setAttribute("aria-expanded","true");document.body.style.overflow="hidden";$("cine-menu-close").focus()}
function closeMenu(){if(!drawerOpen)return;$("cine-menu-backdrop").hidden=true;drawerOpen=false;$("cine-menu-trigger").setAttribute("aria-expanded","false");document.body.style.overflow="";if(oldFocus&&oldFocus.focus)oldFocus.focus()}
function releaseSearch(){const input=$("search");if(input&&input.value){input.value="";input.dispatchEvent(new Event("input",{bubbles:true}))}const all=document.querySelector("#tabs [data-type=all]");if(all)all.click();const sort=$("sort");if(sort&&sort.value!=="relevant"){sort.value="relevant";sort.dispatchEvent(new Event("change"))}}
function setFilter(term){
 setHash("explorer");
 const q=$("search");if(!q)return;
 const category=["films","series","animes"].includes(term)?term:null;
 const all=document.querySelector('#tabs [data-type="all"]');
 if(all&&!all.classList.contains("active"))all.click();
 if(category){
  const button=document.querySelector('#tabs [data-type="'+category+'"]');
  if(button&&!button.classList.contains("active"))button.click();
 }
 q.value=category?"":term;
 q.dispatchEvent(new Event("input",{bubbles:true}));
 setTimeout(()=>q.focus(),50);
}
function buildPanel(name){const s=node("section","cine-panel");s.id="cine-page-"+name;s.dataset.page=name;s.hidden=true;s.setAttribute("aria-label",labels[name]);panel[name]=s;return s}
function heading(p,title,desc){const top=node("div","cine-head");const h=node("h2",null,title);top.append(h);if(desc)top.append(node("p",null,desc));p.append(top)}
function featuredCard(c,label){const b=node("button","cine-pick");b.type="button";const avatar=node("div","cine-pick-avatar");const url=linkAvatar(c);if(url){const img=document.createElement("img");img.loading="lazy";img.decoding="async";img.alt="";showChannelImage(img,url,null,()=>{img.remove();avatar.textContent="🎬"});avatar.append(img)}else avatar.textContent="🎬";
 const title=node("strong",null,c.title);const sub=node("small",null,(c.featured?"✦ À la une · ":"")+(label||"Canal Telegram"));b.append(avatar,title,sub);
 if(c.content_verified&&Number(c.content_count)>=1){const count=node("small","cine-pick-stat",Number(c.content_count).toLocaleString("fr-FR")+" publications");b.append(count)}
 b.onclick=()=>previewChannel(c);return b}
function previewChannel(c){
 if(!c||!Number.isSafeInteger(Number(c.id))||!validChannelLink(c.link))return;
 currentPreview=Number(c.id);
 document.dispatchEvent(new CustomEvent("cineradar:show-preview",{detail:{id:currentPreview,channel:c}}));
}
function quickButton(iconKey,label,term){const b=node("button");b.type="button";const glyph=node("span","icon cine-3d-icon cine-icon-"+iconKey);glyph.setAttribute("aria-hidden","true");b.append(glyph,node("strong",null,label));b.onclick=()=>setFilter(term);return b}
function sectionTitle(parent,title,link,fn){const wrap=node("div","cine-section-title");wrap.append(node("h3",null,title));if(link){const b=node("button","cine-link",link);b.onclick=fn;wrap.append(b)}parent.append(wrap)}
// Hero artwork stays decorative; only verified pinned channel messages appear in À l'affiche.
const PRELOADED_PINS=null;
let posterShowcase=[],pinnedShowcase=Array.isArray(PRELOADED_PINS)?PRELOADED_PINS:[];
const posterTypeTitle={films:"Films",series:"Séries",animes:"Animés"};
const posterFallback=Array.from({length:10},(_,i)=>({title:["Cinéma","Films","Séries","Animés","À découvrir"][i%5],type:["films","films","series","animes"][i%4],poster:null}));
const pinnedLink=url=>/^https:\/\/t\.me\/(?:CineXFilms_vf|seriesvf_cinex|CineXAnimeFR)\/[1-9][0-9]{0,12}$/i.test(String(url||""));
const pinnedImage=url=>/^\/assets\/pin-cover\/(?:films|series|animes)\/[1-9][0-9]{0,12}\.jpg$/.test(String(url||""));
function openPinnedMessage(entry){
 if(!pinnedLink(entry.link))return;
 metric("pin_open","p:"+entry.type+":"+Number(entry.message_id));
 fetch("/api/pinned-click",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({kind:entry.type,message_id:Number(entry.message_id)}),keepalive:true}).catch(()=>{});
 const webapp=window.Telegram?.WebApp;
 if(webapp?.openTelegramLink)webapp.openTelegramLink(entry.link);else window.open(entry.link,"_blank","noopener,noreferrer");
}
function posterTile(entry,hero=false){
 const item=node(hero?"div":"button",hero?"cine-hero-cover":"cine-film-poster");
 if(!hero){item.type="button";item.title="Ouvrir "+entry.title+" sur Telegram";item.setAttribute("aria-label","Voir "+entry.title+" dans le canal Telegram");item.onclick=()=>openPinnedMessage(entry)}
 const mark=node("div","cine-poster-placeholder");mark.append(cineCategoryIcon(entry.type));item.append(mark);
 const external=/^https:\/\/(?:image\.tmdb\.org\/t\/p\/w342\/[A-Za-z0-9_-]{8,100}\.(?:jpe?g|png|webp)|static\.tvmaze\.com\/uploads\/images\/(?:medium_portrait|original_untouched)\/[0-9]+\/[0-9]+\.jpg|(?:m\.media-amazon\.com|images-na\.ssl-images-amazon\.com)\/images\/[A-Za-z0-9_%@.+/-]{8,800})$/.test(String(entry.poster||""));
 if((hero&&external)||(!hero&&pinnedImage(entry.poster)&&pinnedLink(entry.link))){
  const img=node("img");img.alt=hero?"":"Affiche de "+entry.title;img.loading=hero?"eager":"lazy";img.decoding="async";img.src=entry.poster;img.onerror=()=>img.remove();item.append(img)
 }
 const caption=node("span",null,entry.title||posterTypeTitle[entry.type]||"Cinéma");if(!hero)caption.className="cine-pin-label";item.append(caption);
 if(!hero){const label=node("span","cine-pin-kind");label.append(cineCategoryIcon(entry.type),document.createTextNode(entry.type==="animes"?"Animé":entry.type==="series"?"Série":"Film"));item.append(label)}
 return item;
}
function renderCinemaShowcase(){
 const hero=$("cine-hero-collage"),strip=$("cine-poster-strip");
 if(hero){
  hero.textContent="";
  const entries=posterShowcase.length>=6?posterShowcase:posterFallback;
  const track=node("div","cine-marquee-track");const one=entries.slice(0,14);
  for(let round=0;round<2;round++)for(const data of one)track.append(posterTile(data,true));hero.append(track);
 }
 if(strip){
  strip.textContent="";
  if(pinnedShowcase.length){
   const track=node("div","cine-poster-track");const many=pinnedShowcase.length>=7;
   if(!many)track.classList.add("cine-poster-short");
   const count=many?2:1;for(let round=0;round<count;round++)for(const data of pinnedShowcase.slice(0,24))track.append(posterTile(data,false));
   strip.append(track);
  }else strip.append(node("div","cine-pins-empty","Aucune affiche à présenter pour le moment."));
 }
 const note=$("cine-poster-note");
 if(note)note.textContent=pinnedShowcase.length?"Appuie sur une affiche pour voir la publication sur Telegram.":"";
}
async function loadCinemaShowcase(){
 const art=fetch("/api/showcase",{headers:{accept:"application/json"},signal:AbortSignal.timeout(8500)})
  .then(r=>r.ok?r.json():Promise.reject(Error("art unavailable")))
  .then(body=>{
   if(Array.isArray(body.items)){
    posterShowcase=body.items.filter(x=>x&&typeof x.title==="string"&&typeof x.type==="string"&&typeof x.poster==="string").slice(0,24);
   }
  }).catch(()=>{}).finally(renderCinemaShowcase);
 const pins=fetch("/api/pinned-showcase",{headers:{accept:"application/json"},signal:AbortSignal.timeout(12500)})
  .then(r=>r.ok?r.json():Promise.reject(Error("pins unavailable")))
  .then(body=>{
   if(Array.isArray(body.items)){
    pinnedShowcase=body.items.filter(x=>x&&["films","series","animes"].includes(x.type)&&pinnedLink(x.link)&&pinnedImage(x.poster)).slice(0,24);
   }
  }).catch(()=>{}).finally(renderCinemaShowcase);
 await Promise.allSettled([pins,art]);
}

const promoChannels=[
 {handle:"actufoot_mrxp",title:"Actu Foot MRXP",desc:"Actualités, résultats et temps forts du football.",icon:"⚽",kind:"football",url:"https://t.me/actufoot_mrxp"},
 {handle:"ActuCrypto24H",title:"Actu Crypto 24H/7",desc:"Mouvements du marché, annonces et tendances crypto.",icon:"₿",kind:"crypto",url:"https://t.me/ActuCrypto24H"},
 {handle:"mrxpronosfr",title:"MR X PRONOS FR",desc:"Pronostics et analyses de rencontres. 18+ · Joue responsablement.",icon:"📊",kind:"pronos",url:"https://t.me/mrxpronosfr"}
];
let promoProfiles=null,promoStarted=false;
function promoCard(info){
 const a=node("a","cine-promo-card");
 a.href=info.url;a.target="_blank";a.rel="noopener noreferrer";
 a.dataset.promoHandle=info.handle;
 a.setAttribute("aria-label","Découvrir "+info.title+" sur Telegram");
 a.onclick=e=>{
  metric("promo_open",info.handle);
  const tg=window.Telegram?.WebApp;
  if(tg?.openTelegramLink){e.preventDefault();tg.openTelegramLink(info.url)}
 };
 const avatar=node("div","cine-promo-avatar",info.icon);
 const img=document.createElement("img");
 img.alt="Photo du canal "+info.title;img.loading="lazy";img.decoding="async";
 img.src="/assets/promo-avatar/"+info.handle+".jpg";
 img.onerror=()=>img.remove();
 avatar.append(img);
 const copy=node("div","cine-promo-copy");
 const name=node("strong",null,info.title);name.classList.add("cine-promo-name");
 const desc=node("small",null,info.desc);desc.classList.add("cine-promo-description");
 copy.append(name,desc);
 if(info.kind==="pronos")copy.append(node("small","cine-promo-age","18+ · Joue responsablement"));
 a.append(avatar,copy,node("span","cine-promo-arrow","↗"));
 return a;
}
function promoBlock(){
 const wrapper=node("aside","cine-promo-slot");wrapper.setAttribute("aria-label","Nos autres canaux Telegram");
 const header=node("div","cine-promo-head");
 header.append(node("strong",null,"À découvrir aussi"),node("small",null,"Nos autres canaux · Promotion"));
 const track=node("div","cine-promo-track");
 const profiles=promoProfiles||[];
 // Three complete sets allow a seamless circular scroll on mobile and desktop.
 // Only the first set is keyboard accessible; duplicate cards remain clickable.
 for(let repeat=0;repeat<3;repeat++)for(const base of promoChannels){
  const profile=profiles.find(p=>p.handle===base.handle);
  const card=promoCard({...base,title:profile?.name||base.title,desc:profile?.description||base.desc});
  if(repeat>0){card.classList.add("cine-promo-duplicate");card.setAttribute("aria-hidden","true");card.tabIndex=-1;}
  track.append(card);
 }
 wrapper.append(header,track);
 if(!promoStarted){
  promoStarted=true;
  fetch("/api/partner-promos",{headers:{accept:"application/json"},signal:AbortSignal.timeout(8500)})
   .then(r=>r.ok?r.json():Promise.reject(Error("Partner profiles unavailable")))
   .then(data=>{
    if(!Array.isArray(data.items))return;
    promoProfiles=data.items.filter(p=>promoChannels.some(c=>c.handle===p.handle));
    for(const profile of promoProfiles){
     for(const card of document.querySelectorAll(".cine-promo-card")){
      if(card.dataset.promoHandle!==profile.handle)continue;
      const name=card.querySelector(".cine-promo-name"),description=card.querySelector(".cine-promo-description");
      if(name&&typeof profile.name==="string")name.textContent=profile.name.slice(0,68);
      if(description&&typeof profile.description==="string")description.textContent=profile.description.slice(0,160);
     }
    }
   }).catch(()=>{});
 }
 return wrapper;
}


const ANALYTICS_DISABLED_KEY="cine-radar-analytics-off";
const ANALYTICS_ID_KEY="cine-radar-visitor-id-v1";
function metricsAllowed(){
 try{return navigator.doNotTrack!=="1"&&localStorage.getItem(ANALYTICS_DISABLED_KEY)!=="1"}catch{return false}
}
function metric(event,target){
 if(!metricsAllowed())return;
 const payload={event};if(target!==undefined)payload.target=String(target);
 fetch("/api/analytics/event",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(payload),keepalive:true}).catch(()=>{});
}
function visitorTracking(){
 if(!metricsAllowed()||!window.crypto?.randomUUID)return;
 let id;
 try{
  id=localStorage.getItem(ANALYTICS_ID_KEY);
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[4-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(id||""))){id=crypto.randomUUID();localStorage.setItem(ANALYTICS_ID_KEY,id)}
 }catch{return}
 const send=event=>fetch("/api/analytics/event",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({event,id}),keepalive:true}).catch(()=>{});
 send("visit");
 setInterval(()=>{if(!document.hidden&&metricsAllowed())send("ping")},70000);
}
function shareCineRadar(){
 const url="https://t.me/CineRadarFr_Bot";
 const text="🍿 Ciné Radar : ton cinéma sur Telegram ! Films, séries, animés et canaux réunis au même endroit. 🎬 Découvre la Mini App 👇";
 metric("share","bot");
 const shareUrl="https://t.me/share/url?url="+encodeURIComponent(url)+"&text="+encodeURIComponent(text);
 const tg=window.Telegram?.WebApp;
 if(tg?.openTelegramLink)tg.openTelegramLink(shareUrl);
 else window.open(shareUrl,"_blank","noopener,noreferrer");
}
function communityTools(home){
 const aside=node("div","cine-community");
 const btn=node("button","cine-community-share");btn.type="button";btn.append(cineNavIcon("partager"),document.createTextNode("Partager Ciné Radar"));btn.onclick=shareCineRadar;
 aside.append(btn,node("small",null,"Tu apprécies Ciné Radar ? Fais-le découvrir à tes proches."));
 home.append(aside);
 let visits=0;
 try{visits=Number(localStorage.getItem("cine-radar-app-visits-v1")||0)+1;localStorage.setItem("cine-radar-app-visits-v1",String(Math.min(visits,9999)))}catch{}
 if(visits<2)return;
 try{if(localStorage.getItem("cine-radar-rating-done-v1"))return}catch{}
 const box=node("div","cine-community-rating");
 const msg=node("span",null,"Tu aimes Ciné Radar ? Donne une note ⭐");
 const buttons=node("div","cine-rating-buttons");
 for(let i=1;i<=5;i++){
  const b=node("button",null,"★"+i);b.type="button";b.setAttribute("aria-label",i+" étoiles");
  b.onclick=()=>{metric("rating",i);box.textContent="Merci pour ton avis ! ❤️";try{localStorage.setItem("cine-radar-rating-done-v1",String(i))}catch{}};
  buttons.append(b);
 }
 const later=node("button","cine-rate-later","Plus tard");later.type="button";
 later.onclick=()=>{box.remove();try{localStorage.setItem("cine-radar-rating-done-v1","later")}catch{}};
 box.append(msg,buttons,later);home.append(box);
}
function analyticsPreference(about){
 const controls=node("div","cine-helper");
 controls.append(node("h3",null,"Choix de confidentialité"),node("p",null,"Nous comptons les visites et certains clics pour améliorer Ciné Radar, sans enregistrer ton nom ni tes messages Telegram. Tu peux désactiver ces statistiques."));
 const opt=node("button","cine-soft-button");opt.type="button";
 const update=()=>{opt.textContent=metricsAllowed()?"Désactiver les statistiques":"Autoriser les statistiques";};
 opt.onclick=()=>{
  try{
   const enabled=metricsAllowed();
   localStorage.setItem(ANALYTICS_DISABLED_KEY,enabled?"1":"0");
   if(enabled)localStorage.removeItem(ANALYTICS_ID_KEY);
   else visitorTracking();
  }catch{}
  update();
 };
 update();controls.append(opt);about.append(controls);
}
let promoTimer=null;
function autoScrollPromos(){
 const track=$("cine-home-picks")?.querySelector(".cine-promo-track");
 if(promoTimer!==null){clearInterval(promoTimer);promoTimer=null}
 if(!track||window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches)return;
 let hovered=false,pausedUntil=0;
 track.addEventListener("mouseenter",()=>{hovered=true});
 track.addEventListener("mouseleave",()=>{hovered=false});
 const pause=()=>{pausedUntil=Date.now()+4500;};
 for(const event of ["pointerdown","touchstart","wheel"])track.addEventListener(event,pause,{passive:true});
 promoTimer=setInterval(()=>{
  if(document.hidden||hovered||Date.now()<pausedUntil||track.matches(":focus-within"))return;
  const nextSet=track.children[promoChannels.length],first=track.children[0];
  if(!nextSet||!first)return;
  const cycle=nextSet.offsetLeft-first.offsetLeft;
  if(cycle<=0||track.scrollWidth-track.clientWidth<cycle)return;
  if(track.scrollLeft>=cycle)track.scrollLeft-=cycle;
  track.scrollLeft+=1;
 },50);
}
function miniFeatured(){
 const a=$("cine-home-picks");if(!a)return;a.textContent="";
 const measure=c=>(c.avatar_verified?200:0)+(c.content_verified?35:0)
   +Math.min(115,Math.log1p(Math.max(0,Number(c.content_count)||0))*16)
   +Math.min(30,(Number(c.posts_7d)||0)*3);
 const featured=catalog.filter(c=>c.featured&&c.title).sort((a,b)=>measure(b)-measure(a)||a.id-b.id);
 const chosen=featured.slice(0,9);
 // Keep every media universe represented when it has a genuinely listed channel.
 for(const type of ["films","series","animes"]){
  if(chosen.some(c=>c.type===type))continue;
  const extra=featured.find(c=>c.type===type&&!chosen.includes(c));
  if(extra){if(chosen.length>=9)chosen.pop();chosen.push(extra)}
 }
 chosen.sort((a,b)=>measure(b)-measure(a)||a.id-b.id);
 if(!chosen.length)chosen.push(...catalog.filter(c=>c.title).slice(0,6));
 const promoAfter=(window.matchMedia?.("(min-width: 690px)")?.matches?6:4);
 for(const [index,c] of chosen.entries()){
  a.append(featuredCard(c,c.type==="films"?"Films":c.type==="series"?"Séries":"Animés"));
  if(index+1===Math.min(promoAfter,chosen.length))a.append(promoBlock());
 }
 if(!chosen.length)a.append(node("div","cine-empty-spot","Chargement des canaux…"));
 autoScrollPromos();

}
function discover(){
 const grid=$("cine-discover-grid");if(!grid)return;grid.textContent="";
 const cats={};for(const id of favorites){const c=catalog.find(c=>c.id===id);if(c)cats[c.type]=(cats[c.type]||0)+1}
 const scored=catalog.filter(c=>!favorites.includes(c.id)).map(c=>{let score=(cats[c.type]||0)*6;if(c.featured)score+=(c.avatar_verified?38:4)+(c.content_verified?10:0)+Math.min(35,Math.log1p(Math.max(0,Number(c.content_count)||0))*6);score+=Math.min(6,Number(c.review_count||0));if(c.link_status==="reachable")score+=2;if(c.last_post_at&&Date.now()-Date.parse(c.last_post_at)<30*86400000)score+=2;return{c,score}}).sort((a,b)=>b.score-a.score||a.c.id-b.c.id).slice(0,12);
 for(const {c} of scored)grid.append(featuredCard(c,c.type==="films"?"Films":c.type==="series"?"Séries":"Animés"));
 if(!scored.length)grid.append(node("div","cine-empty-spot","Aucun autre canal à suggérer actuellement."));
 const title=$("cine-discover-title");if(title)title.textContent=favorites.length?"Selon tes favoris":"Quelques canaux à explorer";
}
function genreContent(){
 const grid=$("cine-genres");grid.textContent="";
 const options=[
  ["films","Films","films",c=>c.type==="films"],["series","Séries","series",c=>c.type==="series"],
  ["animes","Animés","animes",c=>c.type==="animes"],["action","Action","action",c=>/action/i.test(c.title+" "+c.genre)],
  ["romance","Romance","romance",c=>/romanti|romance/i.test(c.title+" "+c.genre)],
  ["africain","Films africains","africain",c=>/nigerian|nigerien|africain|nollywood/i.test(c.title+" "+c.genre)],
  ["vostfr","VOSTFR","vostfr",c=>/vostfr/i.test(c.title+" "+c.language)],
  ["turc","Séries turques","turc",c=>/turc/i.test(c.title+" "+c.genre)],
  ["drame","Drame","drama",c=>/drama|drame/i.test(c.title+" "+c.genre)]
 ];
 for(const [iconKey,label,query,check] of options){
  const count=catalog.filter(check).length;if(!count)continue;
  const b=node("button","cine-genre-tile");b.type="button";
  const head=node("span","cine-genre-label");head.append(cineCategoryIcon(iconKey),node("strong",null,label));
  b.append(head,node("small",null,count+(count===1?" canal":" canaux")+" dans l’annuaire"));
  b.onclick=()=>setFilter(query);grid.append(b);
 }
}
function cardDecorate(){
 const root=$("cards");if(!root)return;
 for(const card of root.querySelectorAll("article[data-channel-id]")){
  const id=Number(card.dataset.channelId);
  const c=catalog.find(x=>x.id===id);
  const rating=card.querySelector(".card-rating");
  if(rating&&!c?.review_count){rating.textContent="Sans avis";rating.classList.add("cine-rating-empty")}
  if(!card.querySelector(".cine-save")){
   const save=node("button","cine-save");save.type="button";save.setAttribute("aria-label","Enregistrer ce canal dans mes favoris");save.onclick=()=>toggleFavorite(id);card.querySelector(".card-body")?.append(save);
  }
  const saved=card.querySelector(".cine-save");if(saved)favoriteLabel(saved,favorites.includes(id));
 }
 filterCards();
}
function filterCards(){
 const root=$("cards");if(!root)return;
 let visible=0;
 for(const c of root.querySelectorAll("article[data-channel-id]")){const id=Number(c.dataset.channelId);const show=mode==="favoris"?favorites.includes(id):mode==="historique"?recent.includes(id):true;c.hidden=!show;if(show)visible++}
 const h=$("heading"),counter=$("count");
 if(h&&mode==="favoris")h.textContent="Mes favoris";
 else if(h&&mode==="historique")h.textContent="Récemment consultés";
 else if(h)h.textContent=$("search")?.value?.trim()?"Résultats de recherche":"Les canaux";
 if(counter)counter.textContent=visible+" cana"+(visible===1?"l":"ux");
 const empty=$("cine-private-empty");if(empty)empty.hidden=mode==="explorer"||visible!==0; if(empty&&!empty.hidden)empty.textContent=mode==="favoris"?"Tu n’as aucun favori. Explore les canaux et utilise « Ajouter aux favoris ».":"Aucun canal consulté pour le moment.";
}
function toggleFavorite(id){favorites=favorites.includes(id)?favorites.filter(x=>x!==id):[id,...favorites].slice(0,250);persist();cardDecorate();discover();const b=$("cine-preview-save");if(b&&currentPreview===id)favoriteLabel(b,favorites.includes(id),true)}
function recordOpen(id){if(!Number.isSafeInteger(id)||id<1)return;metric("channel_open","c:"+id);const first=!recent.includes(id);recent=[id,...recent.filter(x=>x!==id)].slice(0,60);persist();if(first){fetch("/api/engagement",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({event:"open",id}),keepalive:true}).catch(()=>{})}filterCards()}
function previewInfo(){
 const sheet=$("sheet");if(!sheet||!sheet.querySelector(".sheet-detail"))return;
 const detail=sheet.querySelector(".sheet-detail");
 if(detail.querySelector("#cine-preview-meta"))return;
 const c=catalog.find(x=>x.id===currentPreview)||catalog.find(x=>x.title===detail.querySelector(".sheet-name h3")?.textContent);
 if(!c)return;
 const box=node("div","cine-meta");box.id="cine-preview-meta";
 const fields=[];
 if(c.genre&&c.genre!=="general")fields.push("Genre : "+c.genre);
 if(c.language&&c.title.toLowerCase().includes("vf"))fields.push("Langue : "+c.language);
 if(c.review_count)fields.push("Avis : "+c.review_count+" · "+Number(c.rating).toFixed(1)+"/5");
 else fields.push("Aucun avis publié pour le moment");
  if(c.last_post_at){const date=Date.parse(c.last_post_at);if(Number.isFinite(date))fields.push("Dernière activité : "+new Date(date).toLocaleDateString("fr-FR"))}
 fields.forEach(v=>box.append(node("div",null,v)));
 const open=detail.querySelector(".sheet-open");if(open)detail.insertBefore(box,open);else detail.append(box);
 const save=node("button","cine-soft-button");save.id="cine-preview-save";favoriteLabel(save,favorites.includes(c.id),true);save.onclick=()=>toggleFavorite(c.id);
 if(open)open.insertAdjacentElement("afterend",save);else detail.append(save);
}
function goToList(modeName){
 mode=modeName;
 const place=$("cine-slot-"+modeName),target=$("cine-listing");
 if(place&&target&&target.parentElement!==place)place.append(target);
 if(modeName!=="explorer")releaseSearch();
 cardDecorate();
}
function navigate(name){
 const p=pages.includes(name)?name:"accueil";closeMenu();
 if(["explorer","favoris","historique"].includes(p))goToList(p);
 switchPanel(p);
 if(p==="decouvrir"){discover();genreContent()}
 if(p==="accueil")miniFeatured();
}

function build(){
 const root=document.querySelector("main.page"),brand=root?.querySelector(".brand"),hero=root?.querySelector(".hero"),nav=$("tabs"),search=document.querySelector("label.search"),tools=root?.querySelector(".v2-tools"),head=root?.querySelector(".heading"),cards=$("cards"),footer=root?.querySelector(".footer");
 if(!root||!brand||!hero||!nav||!search||!tools||!head||!cards)return;
 const menuBtn=node("button","cine-menu-trigger");menuBtn.append(cineNavIcon("menu"));menuBtn.id="cine-menu-trigger";menuBtn.type="button";menuBtn.setAttribute("aria-label","Ouvrir le menu");menuBtn.setAttribute("aria-expanded","false");menuBtn.onclick=openMenu;brand.append(menuBtn);
 const panels=pages.map(buildPanel);footer.before(...panels);
 const home=panel.accueil;hero.classList.add("cine-hero");home.append(hero);
 const art=hero.querySelector(".hero-art");if(art){const collage=node("div","cine-hero-collage");collage.id="cine-hero-collage";art.append(collage)}
 const copy=hero.querySelector(".hero-copy");if(copy){const h=copy.querySelector("h2"),p=copy.querySelector("p");if(h){h.textContent="";h.append("Le cinéma,",node("span","accent","à découvrir."))}if(p)p.textContent="Trouve facilement les canaux Telegram qui correspondent à tes envies."}
 const showcaseSection=node("section","cine-poster-section");showcaseSection.setAttribute("aria-label","Affiches de films et séries");const showcaseHead=node("div","cine-poster-section-title");const showcaseLabel=node("strong");showcaseLabel.append(cineCategoryIcon("affiches"),document.createTextNode("À l'affiche"));showcaseHead.append(showcaseLabel,node("small",null,"Films · Séries · Animés"));const posterWindow=node("div","cine-poster-window");posterWindow.id="cine-poster-strip";const attribution=node("p","cine-poster-note");attribution.id="cine-poster-note";showcaseSection.append(showcaseHead,posterWindow,attribution);home.append(showcaseSection);renderCinemaShowcase();loadCinemaShowcase();

 const form=node("form","cine-home-search");form.setAttribute("role","search");const inp=document.createElement("input");inp.type="search";inp.placeholder="Films d'action, animés, séries…";inp.setAttribute("aria-label","Rechercher des canaux");const submit=node("button",null,"Chercher");submit.type="submit";form.append(inp,submit);form.onsubmit=e=>{e.preventDefault();setFilter(inp.value.trim())};home.append(form);
 sectionTitle(home,"Explore par univers",null);
 const quick=node("div","cine-quick");quick.append(quickButton("film","Films","films"),quickButton("tv","Séries","series"),quickButton("gamepad","Animés","animes"));home.append(quick);
 sectionTitle(home,"À découvrir","Voir tout",()=>setHash("decouvrir"));const picks=node("div","cine-home-picks");picks.id="cine-home-picks";home.append(picks);
 const help=node("p","cine-home-footer","Choisis un canal pour l’ouvrir directement sur Telegram.");home.append(help);
 communityTools(home);
 visitorTracking();
 // Explorer : recherche, filtres repliés et liste
 heading(panel.explorer,"Explorer les canaux","Recherche un canal, un genre ou un mot-clé.");panel.explorer.append(search);
 const details=node("details","cine-explore-options");const summary=node("summary",null,"Filtres avancés et tri");details.append(summary,nav,tools);panel.explorer.append(details);
 const genres=node("div","cine-genre-chips");genres.id="cine-genre-chips";panel.explorer.append(genres);
 // La liste est déplacée selon Explorer / Favoris / Historique
 listing=node("div");listing.id="cine-listing";listing.append(head,cards);
 const empty=node("div","cine-private-empty");empty.id="cine-private-empty";empty.hidden=true;listing.append(empty);
 for(const name of ["explorer","favoris","historique"]){const slot=node("div");slot.id="cine-slot-"+name;panel[name].append(slot)}
 $("cine-slot-explorer").append(listing);
 heading(panel.favoris,"Mes favoris","Les canaux enregistrés restent dans ce navigateur.");
 heading(panel.historique,"Consultés récemment","Retrouve les canaux ouverts depuis ce navigateur.");
 panel.favoris.prepend(panel.favoris.querySelector(".cine-head"));
 panel.historique.prepend(panel.historique.querySelector(".cine-head"));
 const clr=node("button","cine-soft-button","Effacer mon historique");clr.onclick=()=>{recent=[];persist();filterCards()};panel.historique.querySelector(".cine-head").append(clr);
 heading(panel.decouvrir,"Découvrir","Explore par thème ou découvre de nouveaux canaux.");

 sectionTitle(panel.decouvrir,"Genres et catégories",null);const genreGrid=node("div","cine-genre-grid");genreGrid.id="cine-genres";panel.decouvrir.append(genreGrid);
 sectionTitle(panel.decouvrir,"Quelques suggestions",null);panel.decouvrir.querySelector(".cine-section-title:last-of-type")?.querySelector("h3")?.setAttribute("id","cine-discover-title");
 const disGrid=node("div","cine-discover-grid");disGrid.id="cine-discover-grid";panel.decouvrir.append(disGrid);
 heading(panel.proposer,"Participer","Contribue à améliorer l’annuaire.");
 const contribute=node("div","cine-helper");contribute.append(node("h3",null,"Tu connais un bon canal ?"),node("p",null,"Partage son lien Telegram pour nous le proposer. Ouvre Ciné Radar depuis Telegram pour participer."));
 const suggest=$("suggest");if(suggest){contribute.append(suggest);suggest.replaceChildren(cineNavIcon("proposer"),document.createTextNode("Proposer un canal"))}panel.proposer.append(contribute);
 const report=node("div","cine-helper");report.append(node("h3",null,"Signaler un problème"),node("p",null,"Ouvre la fiche d’un canal pour signaler un lien cassé, une mauvaise catégorie, du spam ou une atteinte aux droits."));const bBrowse=node("button",null,"Parcourir les canaux");bBrowse.onclick=()=>setHash("explorer");report.append(bBrowse);panel.proposer.append(report);
 heading(panel.apropos,"À propos de Ciné Radar","Un annuaire indépendant de canaux publics Telegram.");
 const about=node("div","cine-helper");about.append(node("h3",null,"Comment utiliser Ciné Radar ?"),node("p",null,"Explore les films, séries et animés, consulte la fiche d’un canal et ouvre-le dans Telegram. Ciné Radar ne fournit pas les vidéos et ne garantit pas les contenus des autres canaux."),node("h3",null,"Donner son avis ou signaler un problème"),node("p",null,"Ouvre la fiche d’un canal depuis Telegram pour laisser un avis ou signaler un problème."),node("h3",null,"Tes données"),node("p",null,"Tes favoris et ton historique restent dans ce navigateur. Tu peux les effacer ci-dessous. Nous ne conservons pas le texte de tes recherches."));
 analyticsPreference(about);
 const wipe=node("button","cine-soft-button","Supprimer mes favoris et mon historique");wipe.onclick=()=>{favorites=[];recent=[];persist();cardDecorate();discover();wipe.textContent="Données locales effacées"};about.append(wipe);panel.apropos.append(about);
 // Navigation en tiroir
 const backdrop=node("div","cine-drawer-backdrop");backdrop.id="cine-menu-backdrop";backdrop.hidden=true;
 const drawer=node("aside","cine-drawer");drawer.setAttribute("role","dialog");drawer.setAttribute("aria-modal","true");drawer.setAttribute("aria-label","Menu de navigation");
 const dhead=node("div","cine-drawer-title");dhead.append(node("b",null,"Ciné Radar"));const close=node("button");close.append(cineNavIcon("fermer"));close.id="cine-menu-close";close.setAttribute("aria-label","Fermer le menu");close.onclick=closeMenu;dhead.append(close);drawer.append(dhead);
 const groups=[["Découvrir",[["Accueil","accueil","accueil"],["Explorer les canaux","explorer","explorer"],["Genres et découvertes","decouvrir","decouvrir"]]],["Personnel",[["Mes favoris","favoris","favoris"],["Historique","historique","historique"]]],["Communauté",[["Proposer un canal","proposer","proposer"],["À propos et confidentialité","apropos","apropos"]]]];
 for(const [label,entries] of groups){drawer.append(node("div","cine-drawer-subtitle",label));for(const [title,page,icon] of entries){const item=makeNav(title,page,icon);item.classList.add("cine-drawer-link");drawer.append(item)}}
 drawer.append(node("p","cine-drawer-foot","Ciné Radar · Films, séries, animés"));backdrop.append(drawer);document.body.append(backdrop);backdrop.addEventListener("click",e=>{if(e.target===backdrop)closeMenu()});
 const bottom=node("nav","cine-bottom-nav");bottom.setAttribute("aria-label","Navigation principale");for(const [title,page,icon] of [["Accueil","accueil","accueil"],["Explorer","explorer","explorer"],["Favoris","favoris","favoris"]])bottom.append(makeNav(title,page,icon));const menu=makeNav("Menu","accueil","menu");menu.onclick=openMenu;menu.removeAttribute("data-go");bottom.append(menu);document.body.append(bottom);
 document.addEventListener("keydown",e=>{if(e.key==="Escape"&&drawerOpen){e.preventDefault();closeMenu()}});
 $("cards").addEventListener("click",e=>{const parent=e.target.closest("article[data-channel-id]");if(!parent)return;const id=Number(parent.dataset.channelId);if(e.target.closest(".view"))currentPreview=id;if(e.target.closest(".open"))recordOpen(id)},true);
 $("sheet").addEventListener("click",e=>{if(e.target.closest(".sheet-open"))recordOpen(currentPreview)},true);
 new MutationObserver(()=>cardDecorate()).observe(cards,{childList:true});
 new MutationObserver(()=>previewInfo()).observe($("sheet"),{childList:true,subtree:false});
 /* navigation handled by the router */
 root.querySelector(".v2-tools #suggest")?.remove();
 const chipConfigs=[["Action","action","action"],["Romance","romance","romance"],["Animés VF","animes vf","animes"],["Séries turques","turc","turc"],["Films africains","africain","africain"]];
 for(const [title,term,iconKey] of chipConfigs){const chip=node("button");chip.type="button";chip.append(cineCategoryIcon(iconKey),document.createTextNode(title));chip.onclick=()=>setFilter(term);genres.append(chip)}
 search.querySelector("input").placeholder="Nom du canal, action, romance…";
 // Hide legacy footer when viewing other pages; retain in DOM for attribution.
 footer.textContent="Ciné Radar · Films, séries et animés";
 window.addEventListener("hashchange",()=>navigate(location.hash.slice(2)));
 navigate(location.hash.slice(2));
 cardDecorate();

 const embedded=window.__CINERADAR_INITIAL_CATALOG__;
 if(Array.isArray(embedded)&&embedded.length){
  catalog=embedded.filter(c=>Number.isSafeInteger(Number(c.id)));
  miniFeatured();discover();genreContent();cardDecorate();
 }
 fetch("/api/catalog?limit=80",{cache:"no-store"}).then(r=>r.ok?r.json():Promise.reject()).then(d=>{catalog=(d.channels||[]).filter(c=>Number.isSafeInteger(Number(c.id)));miniFeatured();discover();genreContent();cardDecorate();const rated=document.querySelector("#sort option[value=\\\"rated\\\"]");if(rated){const any=catalog.some(c=>c.review_count>0);rated.disabled=!any;rated.textContent=any?"Mieux notés":"Notes à venir"}}).catch(()=>{miniFeatured();cardDecorate()});
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",build,{once:true});else build();
})();

</script>
</body>
</html>`;