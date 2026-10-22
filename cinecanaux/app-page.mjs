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
.search-clear .icon{width:13px;height:13px}
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
.cover-illustration{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.cover-illustration svg{width:100%;height:100%;display:block}
.card[data-type="series"] .card-cover{background:linear-gradient(145deg,#182858,#3f255b)}
.card[data-type="animes"] .card-cover{background:linear-gradient(135deg,#22285a,#81385d)}
.card-body{padding:10px 9px 9px}
.card h4{font-size:clamp(11px,2.8vw,13.2px);font-weight:800;line-height:1.28;letter-spacing:-.18px;margin:0;min-height:31px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}
.card-kind{display:flex;align-items:center;color:#a0b5d6;font-size:10px;margin:3px 0 10px;gap:4px}
.card-actions{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.card-actions button{display:flex;justify-content:center;align-items:center;min-width:0;gap:3px;border-radius:8px;height:31px;border:1px solid transparent;font-size:clamp(10px,2.35vw,12px);font-weight:750;padding:0 2px;white-space:nowrap}
.card-actions .icon{height:13px;width:13px}
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
const telegram=()=>window.Telegram?.WebApp||null;
document.addEventListener("DOMContentLoaded",()=>{try{telegram()?.ready();telegram()?.expand();}catch{}});
const $=id=>document.getElementById(id);
const validLink=url=>/^https:\/\/t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?$/.test(String(url||""));
const photoHost=url=>/^https:\/\/(?:[a-z0-9-]+\.)*(?:telesco\.pe|telegram\.org|telegram-cdn\.org|t\.me)\/[^\s"'<>]{1,1200}$/i.test(String(url||""));
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
function ico(key){const holder=document.createElement("span");holder.className="icon";holder.setAttribute("aria-hidden","true");holder.innerHTML='<svg viewBox="0 0 24 24">'+(icons[key]||icons.film)+'</svg>';return holder;}
document.querySelectorAll("[data-icon]").forEach(x=>x.replaceWith(ico(x.dataset.icon)));
let type="all",query="",channels=[],allChannels=[],lastFetch=0,fetchPending=null,images=new Map(),inFlight=new Map(),previewToken=0,thumbQueue=[],thumbActive=0;
const MAX_THUMB_FETCH=2;
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
 if(photoHost(c.photo)){const img=node("img");img.alt="Photo publique du canal "+c.title;img.loading="lazy";img.decoding="async";img.onerror=()=>img.remove();img.src=c.photo;cover.append(img);}
 const body=node("div","card-body");body.append(node("h4",null,c.title));
 body.append(node("div","card-kind",typeLabel(c.type)));
 const actions=node("div","card-actions");
 actions.append(button("Aperçu","view",()=>showPreview(c),"eye"),button("Ouvrir","open",()=>openTelegram(c.link),"external"));
 body.append(actions);card.append(cover,body);
 card.setAttribute("aria-label",c.title);
 return card;
}
function render(){
 const root=$("cards");root.textContent="";
 $("count").textContent=channels.length+" canal"+(channels.length>1?"aux":"");
 $("heading").textContent=query.trim()?"Résultats de recherche":"Les canaux";
 if(!channels.length){
  const empty=node("div","empty");empty.append(node("strong",null,"Aucun canal trouvé"),document.createTextNode("Essaie une autre recherche ou une autre catégorie."));
  root.append(empty);return;
 }
 const fragment=document.createDocumentFragment();
 channels.forEach((c,i)=>fragment.append(buildCard(c,i)));
 root.append(fragment);
}
function updatePreviewThumb(id,p){
 images.set(id,p);
 const source=allChannels.find(x=>x.id===id);
 if(!source)return;
 const url=[p.post_image,p.photo].find(photoHost);
 if(!url)return;
 source.photo=url;
 const cover=Array.from($("cards").children).find(x=>Number(x.dataset.channelId)===id)?.querySelector(".card-cover");
 if(cover&&!cover.querySelector("img")){
  const img=node("img");img.alt="Photo publique du canal "+source.title;img.loading="lazy";img.decoding="async";img.onerror=()=>img.remove();img.src=url;cover.append(img);
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
 const key=query.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase().trim();
 channels=allChannels.filter(c=>(type==="all"||c.type===type)&&(!key||(String(c.title)+" "+String(c.genre||"")).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase().includes(key)));
 render();enqueueVisiblePhotos();
}
async function load(force=false){
 if(allChannels.length)applyFilters();
 if(fetchPending)return fetchPending;
 if(!force&&allChannels.length&&Date.now()-lastFetch<120000)return;
 if(!allChannels.length){$("count").textContent="…";$("cards").textContent="";$("cards").append(node("div","empty loading","Chargement des canaux…"));}
 fetchPending=(async()=>{
  try{const result=await api("/api/catalog");allChannels=result.channels||[];lastFetch=Date.now();applyFilters();}
  catch{if(!allChannels.length){$("cards").textContent="";const error=node("div","empty");error.append(node("strong",null,"Connexion momentanément indisponible"),document.createTextNode("Choisis une catégorie pour réessayer."));$("cards").append(error);}}
  finally{fetchPending=null;}
 })();
 return fetchPending;
}
function fillPreview(c,p){
 const sheet=$("sheet");sheet.textContent="";
 const bar=node("div","sheet-head");const back=button("Retour","sheet-back",close,"back");
 bar.append(back,node("span",null,"Ciné Radar · Aperçu"));sheet.append(bar);
 const visual=node("div","sheet-visual");visual.append(makeArt(c.type,"preview-"+c.id));
 const url=[p?.post_image,p?.photo,c.photo].find(photoHost);
 if(url){const img=node("img");img.alt="Image publique du canal "+c.title;img.decoding="async";img.onerror=()=>img.remove();img.src=url;visual.append(img);}
 sheet.append(visual);
 const detail=node("div","sheet-detail");
 const profile=node("div","sheet-profile");
 const avatar=node("div","sheet-avatar");avatar.append(ico(c.type==="series"?"tv":c.type==="animes"?"gamepad":"film"));
 if(photoHost(p?.photo)){avatar.textContent="";const img=node("img");img.alt="Photo du canal";img.src=p.photo;img.onerror=()=>{avatar.textContent="";avatar.append(ico("film"));};avatar.append(img);}
 const names=node("div","sheet-name");names.append(node("h3",null,p?.title||c.title),node("small",null,"Canal public Telegram"));
 const tag=node("div","genre-tag",typeLabel(c.type));names.append(tag);profile.append(avatar,names);detail.append(profile);
 const usefulBio=p?.description&&!p.description.startsWith("Canal Telegram public")?p.description:
  "Canal public classé dans « "+typeLabel(c.type)+" ». Consulte ses publications directement sur Telegram.";
 detail.append(node("p","sheet-description",usefulBio));
 detail.append(button("Ouvrir le canal","sheet-open",()=>openTelegram(c.link),"send"));
 sheet.append(detail);
}
function showPreview(c){
 const token=++previewToken;
 $("overlay").hidden=false;document.body.style.overflow="hidden";
 fillPreview(c,images.get(c.id));
 if(images.has(c.id))return;
 getPreview(c.id).then(p=>{if(token===previewToken&&!$("overlay").hidden)fillPreview(c,p);}).catch(()=>{});
}
for(const b of document.querySelectorAll("[data-type]"))b.onclick=()=>{
 type=b.dataset.type;
 document.documentElement.dataset.scene=type;
 for(const x of document.querySelectorAll("[data-type]")){const active=x===b;x.classList.toggle("active",active);x.setAttribute("aria-pressed",String(active));}
 if(allChannels.length)applyFilters();else load();
};
$("search").oninput=e=>{
 query=e.target.value.slice(0,70);
 $("searchClear").hidden=!query.length;
 if(allChannels.length)applyFilters();
};
$("searchClear").onclick=()=>{$("search").value="";query="";$("searchClear").hidden=true;applyFilters();$("search").focus();};
document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible"&&Date.now()-lastFetch>120000)load(true);});
$("overlay").onclick=e=>{if(e.target===$("overlay"))close();};
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!$("overlay").hidden)close();});
if(Array.isArray(PRELOADED_CATALOG)&&PRELOADED_CATALOG.length){
 allChannels=PRELOADED_CATALOG;lastFetch=Date.now();applyFilters();
}
load();
})();
</script>
</body>
</html>`;
