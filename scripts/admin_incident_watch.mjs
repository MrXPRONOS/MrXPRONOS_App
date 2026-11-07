// GitHub-native scheduler: checks real recent runs, signs its identity via OIDC,
// never puts Supabase credentials or the cron-job.org API key in GitHub.
const repo=process.env.GITHUB_REPOSITORY;
const githubToken=process.env.GITHUB_TOKEN;
if(repo!=="MrXPRONOS/MrXPRONOS_App"||!githubToken)throw Error("Wrong repository or missing GitHub token");
const api=await fetch("https://api.github.com/repos/"+repo+"/actions/runs?branch=main&per_page=100",{
 headers:{"Authorization":"Bearer "+githubToken,
  "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
});
if(!api.ok)throw Error("GitHub workflows unavailable: HTTP "+api.status);
const github=await api.json();
const runs=(github.workflow_runs||[]).map(r=>({
 id:r.id,name:r.name,path:r.path,event:r.event,head_sha:r.head_sha,
 created_at:r.created_at,status:r.status,conclusion:r.conclusion,
 run_attempt:r.run_attempt,html_url:r.html_url
}));
const requestURL=process.env.ACTIONS_ID_TOKEN_REQUEST_URL;
const requestToken=process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN;
if(!requestURL||!requestToken)throw Error("GitHub Actions OIDC not available");
const identity=await fetch(requestURL+"&audience=mrxpronos-admin-watch",{
 headers:{"Authorization":"Bearer "+requestToken}
});
if(!identity.ok)throw Error("OIDC token exchange failed");
const jwt=(await identity.json()).value;
if(!jwt)throw Error("Empty OIDC identity");
const request=await fetch("https://nhwafcpndlufzzxexikh.supabase.co/functions/v1/admin-incident-watch",{
 method:"POST",headers:{"Authorization":"Bearer "+jwt,"Content-Type":"application/json"},
 body:JSON.stringify({runs})
});
const data=await request.json().catch(()=>({}));
if(!request.ok)throw Error("Incident watch HTTP "+request.status+" "+String(data.error||""));
console.log("Contrôle incidents :",JSON.stringify({
 observations:data.observations,changes:data.changes,escalations:data.escalations,
 degraded_sources:data.degraded_sources
}));
if(Number(data.escalations||0)>0){
 console.error("Incidents critiques escaladés. Ouvrir l'administration pour consulter les détails.");
 process.exitCode=1;
}
