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
  function editorial(kind) {
    var isBonus = kind === 'bonus';
    return '<div class="mx-load-card mx-load-editorial'+(isBonus?' mx-load-offer':'')+'" aria-hidden="true">'+
      block('100%','mx-load-image')+
      '<div class="mx-load-editorial-body">'+
        '<div class="mx-load-row mx-load-spread">'+block('32%','mx-load-line mx-load-line--pill mx-load-block--gold')+block('24%','mx-load-line mx-load-line--sm')+'</div>'+
        block('86%','mx-load-line mx-load-line--lg')+
        block('100%','mx-load-line')+
        block('75%','mx-load-line')+
        '<div class="mx-load-separator"></div>'+
        '<div class="mx-load-footer">'+block('44%','mx-load-line')+block('20%','mx-load-line mx-load-line--pill mx-load-block--gold')+'</div></div></div>';
  }
  function article() {
    return '<div class="mx-load-card mx-load-article" aria-hidden="true">'+
      block('100%','mx-load-image mx-load-image--hero')+
      '<div class="mx-load-article-body">'+block('110px','mx-load-line mx-load-line--pill mx-load-block--gold')+
      block('83%','mx-load-line mx-load-line--title')+
      block('65%','mx-load-line mx-load-line--lg')+
      '<div class="mx-load-separator"></div>'+
      block('100%','mx-load-line')+block('96%','mx-load-line')+
      block('99%','mx-load-line')+block('79%','mx-load-line')+
      block('100%','mx-load-line')+block('57%','mx-load-line')+'</div></div>';
  }
  function admin() {
    return '<div class="mx-load-card mx-load-stat" aria-hidden="true">'+
      block('60%','mx-load-line')+block('48%','mx-load-line mx-load-line--title mx-load-block--gold')+
      block('36%','mx-load-line mx-load-line--sm')+'</div>';
  }
  function render(kind, count) {
    kind = ['matches','history','live','news','blog','advice','bonus','article','admin'].includes(kind) ? kind : 'matches';
    count = Math.max(1, Math.min(6, Number(count) || (kind === 'article' ? 1 : 3)));
    var labels = {
      matches:'Chargement des pronostics', history:"Chargement de l'historique",
      live:'Recherche des matchs et signaux LIVE', news:'Chargement des actualités',
      blog:'Chargement des articles', advice:'Chargement des conseils',
      bonus:'Chargement des offres', article:'Ouverture du contenu', admin:'Chargement des statistiques'
    };
    var label = labels[kind];
    var cards = '';
    for (var i = 0; i < count; i++) {
      cards += kind === 'article' ? article() :
        kind === 'admin' ? admin() :
        ['news','blog','advice','bonus'].includes(kind) ? editorial(kind) : card(kind);
    }
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
    mount('top-today-picks', 'matches');
    mount('verified-picks', 'history');
    mount('foot-news-container', 'news');
    mount('blog-list', 'blog');
    mount('conseils-list', 'advice');
    mount('blog-post', 'article');
    mount('conseil-post', 'article');
    mount('bonus-grid', 'bonus');
  }
  window.MXLoading = Object.freeze({ render: render, mount: mount });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
