const branch="feature/bsd-v3-40-markets-shadow-20261022";
const repo="MrXPRONOS/MrXPRONOS_App";
export default {
  async fetch(request){
    const u=new URL(request.url);
    if(request.method!=="GET"&&request.method!=="HEAD")return new Response("Method not allowed",{status:405});
    const path=u.pathname==="/"?"pronos-v3-test.html":decodeURIComponent(u.pathname.replace(/^\//,""));
    if(path.includes("..")||path.includes("\\")||path.startsWith(".")||path.includes("//"))return new Response("Bad path",{status:400});
    const branchOnly=new Set(["pronos-v3-test.html","assets/js/pronos-v3-test.js","bsd/v3_preview_feed.json"]);
    const restricted=(path==="data.json"||path.startsWith("bsd/")&&!branchOnly.has(path)||path==="pronos.html");
    if(restricted)return new Response("Isolated V3 preview only",{status:404});
    const source=branchOnly.has(path)
       ?"https://raw.githubusercontent.com/"+repo+"/refs/heads/"+branch+"/"+path
       :"https://mrxpronos.github.io/MrXPRONOS_App/"+path;
    const response=await fetch(source,{headers:{"Accept":"*/*"}});
    if(!response.ok)return new Response(path==="bsd/v3_preview_feed.json"?"V3 feed not ready":"Preview resource unavailable",{status:response.status});
    const headers=new Headers(response.headers);
    headers.set("X-Robots-Tag","noindex, nofollow, noarchive");
    headers.set("X-MrXpronos-V3-Preview","experimental");
    headers.set("Cache-Control",branchOnly.has(path)?"no-store, max-age=0":"public,max-age=300");
    headers.delete("Set-Cookie");
    if(path.endsWith(".html"))headers.set("Content-Type","text/html; charset=utf-8");
    if(path.endsWith(".js"))headers.set("Content-Type","text/javascript; charset=utf-8");
    if(path.endsWith(".json"))headers.set("Content-Type","application/json; charset=utf-8");
    return new Response(request.method==="HEAD"?null:response.body,{status:response.status,headers});
  }
};
