const CACHE='prono-live-v8';
const ASSETS=['./','./index.html','./assets/styles.css?v=20261006-bonus2','./assets/app.js?v=20261006-bonus2','./assets/favicon.svg','./assets/og-prono-live.webp','./manifest.webmanifest'];

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(c=>c.addAll(ASSETS))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const url=new URL(event.request.url);
  if(url.origin!==location.origin)return;

  event.respondWith((async()=>{
    try{
      const fresh=await fetch(event.request,{cache:'no-store'});
      if(fresh&&fresh.ok){
        const copy=fresh.clone();
        const cache=await caches.open(CACHE);
        cache.put(event.request,copy).catch(()=>{});
      }
      return fresh;
    }catch{
      const cached=await caches.match(event.request);
      if(cached)return cached;
      if(event.request.mode==='navigate')return caches.match('./index.html');
      return Response.error();
    }
  })());
});

self.addEventListener('push',event=>{
  let d={};
  try{d=event.data?.json()||{}}catch{}
  event.waitUntil(self.registration.showNotification(d.title||'Prono Live',{
    body:d.body||'Nouveau pronostic disponible',
    icon:'./assets/favicon.svg',
    badge:'./assets/favicon.svg',
    tag:d.tag||'prono-live',
    requireInteraction:true,
    data:{url:d.url||'./'},
    actions:[{action:'open',title:'Voir le pronostic'},{action:'close',title:'Fermer'}]
  }));
});

self.addEventListener('notificationclick',event=>{
  event.notification.close();
  if(event.action==='close')return;
  const url=event.notification.data?.url||'./';
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{
    for(const c of list)if('focus'in c){c.navigate?.(url);return c.focus()}
    return clients.openWindow?.(url)
  }));
});