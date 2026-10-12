/* Mr XPRONOS — Skeletons réutilisables. Aucune donnée utilisateur injectée. */
(function () {
  "use strict";
  function block(width, extra) {
    return '<span aria-hidden="true" class="mx-load-block '+(extra || 'mx-load-line')+'" style="width:'+width+'"></span>';
  }
  function team() {
    return '<div class="mx-load-team">'+block('38px','mx-load-logo')+block('72%','mx-load-line')+'</div>';
  }
  function card(kind) {
    if (kind === 'history') {
      return '<div class="mx-load-card mx-load-history" aria-hidden="true">'+
        '<div class="mx-load-row mx-load-spread">'+block('112px','mx-load-line mx-load-line--sm')+block('76px','mx-load-line mx-load-line--sm')+'</div>'+
        '<div class="mx-load-teamrow">'+
          '<div class="mx-load-team">'+block('30px','mx-load-logo')+block('68px','mx-load-line')+'</div>'+
          '<div class="mx-load-versus">'+block('66px','mx-load-line mx-load-line--lg')+'</div>'+
          '<div class="mx-load-team">'+block('30px','mx-load-logo')+block('68px','mx-load-line')+'</div>'+
        '</div><div class="mx-load-separator"></div>'+
        '<div class="mx-load-footer">'+block('38%','mx-load-line mx-load-line--sm')+block('73px','mx-load-line mx-load-line--pill mx-load-block--gold')+'</div></div>';
    }
    var live = kind === 'live';
    return '<div class="mx-load-card'+(live?' mx-load-live':'')+'" aria-hidden="true">'+
      '<div class="mx-load-row mx-load-spread">'+block(live?'58px':'100px','mx-load-line mx-load-line--pill mx-load-block--gold')+block('92px','mx-load-line mx-load-line--sm')+'</div>'+
      '<div class="mx-load-teamrow">'+team()+'<div class="mx-load-versus">'+block('40px','mx-load-line mx-load-line--lg mx-load-block--gold')+'</div>'+team()+'</div>'+
      '<div class="mx-load-separator"></div>'+
      '<div class="mx-load-footer">'+block(live?'64%':'49%','mx-load-line')+block(live?'60px':'80px','mx-load-line mx-load-line--pill mx-load-block--gold')+'</div></div>';
  }
  function render(kind, count) {
    kind = ['matches','history','live'].includes(kind) ? kind : 'matches';
    count = Math.max(1, Math.min(6, Number(count) || (kind === 'history' ? 3 : 3)));
    var label = kind === 'history' ? "Chargement de l'historique" :
      kind === 'live' ? 'Recherche des matchs et signaux LIVE' : 'Chargement des pronostics';
    var cards = '';
    for (var i = 0; i < count; i++) cards += card(kind);
    return '<section class="mx-load-group mx-load-group--'+kind+'" role="status" aria-label="'+label+'">'+
      '<div class="mx-load-heading"><span class="mx-load-pulse" aria-hidden="true"></span><span>'+label+'…</span></div>'+
      '<div class="mx-load-grid mx-load-grid--'+kind+'" aria-hidden="true">'+cards+'</div></section>';
  }
  function mount(id, kind) {
    var node = document.getElementById(id);
    if (node && node.querySelector('.loading')) {
      node.innerHTML = render(kind);
    }
  }
  function init() {
    mount('matches-container', 'matches');
    mount('history-container', 'history');
  }
  window.MXLoading = Object.freeze({ render: render, mount: mount });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
