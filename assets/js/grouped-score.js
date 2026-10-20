/* 1xBet grouped exact-score preview. No bet placement and no fabricated prices. */
(() => {
  'use strict';
  const root=document.querySelector('#matches');
  const summary=document.querySelector('#summary');
  const filter=document.querySelector('#camp');
  const search=document.querySelector('#filter-team');
  const statusButtons=[...document.querySelectorAll('[data-status]')];
  let payload={matches:[]};
  let state='upcoming';
  const asText=(v,fallback='—')=>v===null||v===undefined?fallback:String(v);
  const pct=p=>Number.isFinite(p)?(p*100).toFixed(1)+' %':'—';
  function node(tag,cls,content) {
    const e=document.createElement(tag);
    if(cls)e.className=cls;
    if(content!==undefined)e.textContent=asText(content);
    return e;
  }
  function timeFmt(x) {
    if(!x)return 'Horaire non disponible';
    const d=new Date(x);
    return Number.isNaN(d.getTime())?'Horaire non disponible':
      d.toLocaleString('fr-FR',{timeZone:'UTC',day:'2-digit',month:'short',
        hour:'2-digit',minute:'2-digit'})+' UTC';
  }
  function matchCard(m) {
    const wrap=node('article','match');
    const title=node('div','match-top');
    const words=node('div');
    words.append(node('h2','',asText(m.home_team,'Équipe 1')+' – '+
                             asText(m.away_team,'Équipe 2')));
    words.append(node('div','meta',asText(m.league,'Compétition non précisée')+
                                     ' · '+timeFmt(m.kickoff_utc)));
    title.append(words);
    title.append(node('span','chip',m.status==='settled'?'Match terminé':'Avant-match'));
    wrap.append(title);
    const direction=asText(m.direction,'neutral');
    const side=direction==='home'?'1X · Tendance domicile':
               direction==='away'?'X2 · Tendance extérieur':
               direction==='draw'?'X · Nul dominant':'Direction incertaine';
    const pills=node('div','pill-row');
    pills.append(node('span','pill strong',side));
    if(m.h2h_priority)pills.append(node('span','pill','H2H stable'));
    if(m.under25_priority)pills.append(node('span','pill','Under 2,5 favorable'));
    wrap.append(pills);
    const rows=Array.isArray(m.groups)?m.groups:[];
    if(rows.length===0) {
      wrap.append(node('div','small','Aucun groupe répertorié pour ce match.'));
      return wrap;
    }
    let shown=3;
    const list=node('div','group-list');
    const rebuild=() => {
      list.replaceChildren();
      rows.slice(0,shown).forEach(g=>{
        const gbox=node('section','group');
        const head=node('div','group-head');
        head.append(node('span','group-label','Groupe '+asText(g.group_id)));
        head.append(node('span','chip',g.direction_eligible?'Direction cohérente':'À écarter'));
        gbox.append(head);
        const scores=node('div','group-scores');
        (Array.isArray(g.scores)?g.scores:[]).forEach(s=>{
          if(!Array.isArray(s)||s.length!==2)return;
          scores.append(node('span','score',asText(s[0])+'–'+asText(s[1])));
        });
        gbox.append(scores);
        const stats=node('div','group-bottom');
        const left=node('div');
        left.append(node('div','prob',pct(Number(g.probability))));
        left.append(node('div','small','Probabilité estimée par le modèle'));
        stats.append(left);
        const price=g.quote_documented&&Number.isFinite(g.odds)
          ?'Cote observée : '+g.odds.toFixed(2)
          :'Cote 1xBet : non vérifiée';
        stats.append(node('div',g.quote_documented?'state':'warn',price));
        gbox.append(stats);
        if(m.status==='settled'&&typeof g.hit==='number')
          gbox.append(node('div','small',g.hit?'Score groupé réussi':'Score groupé non réalisé'));
        list.append(gbox);
      });
    };
    rebuild();wrap.append(list);
    if(rows.length>3) {
      const btn=node('button','expand','Afficher tous les groupes ('+rows.length+')');
      btn.type='button';
      btn.addEventListener('click',()=>{
        shown=shown===3?rows.length:3;
        btn.textContent=shown===3?'Afficher tous les groupes ('+rows.length+')':'Réduire la liste';
        rebuild();
      });
      wrap.append(btn);
    }
    return wrap;
  }
  function render(){
    const query=search.value.toLocaleLowerCase('fr').trim();
    const dir=filter.value;
    const rows=(Array.isArray(payload.matches)?payload.matches:[]).filter(m=>{
      const completed=m.status==='settled';
      if(state==='history'?!completed:completed)return false;
      if(dir!=='all'&&m.direction!==dir)return false;
      const hay=[m.home_team,m.away_team,m.league].map(x=>String(x||'')).join(' ').toLocaleLowerCase('fr');
      return !query||hay.includes(query);
    });
    summary.textContent=rows.length+' match'+(rows.length!==1?'s':'')+
      ' · Analyses expérimentales · Les cotes absentes ne sont jamais inventées.';
    root.replaceChildren();
    if(!rows.length){
      root.append(node('div','empty',
        state==='history'?'Aucun résultat groupé vérifié dans cet historique.':
        'Aucune sélection 1xBet vérifiée pour le moment. Les premières analyses restent privées.'));
      return;
    }
    rows.forEach(m=>root.append(matchCard(m)));
  }
  statusButtons.forEach(button=>button.addEventListener('click',()=>{
    state=button.dataset.status;
    statusButtons.forEach(b=>b.classList.toggle('active',b===button));
    render();
  }));
  filter.addEventListener('change',render);
  search.addEventListener('input',render);
  fetch('./scores-groupes-preview.json',{cache:'no-store'})
    .then(response=>{if(!response.ok)throw new Error('Aucun flux');return response.json();})
    .then(data=>{if(!data||!Array.isArray(data.matches))throw new Error('Schéma invalide');payload=data;render();})
    .catch(()=>{payload={matches:[]};render();});
})();
