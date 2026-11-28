// Secrets must be supplied through the local environment, not source files.
const {BOT_TOKEN,WEBHOOK_SECRET,WORKER_URL}=process.env;
if(!BOT_TOKEN||!WEBHOOK_SECRET||!WORKER_URL||!/^[-_A-Za-z0-9]{32,256}$/.test(WEBHOOK_SECRET))throw new Error('Set BOT_TOKEN, WEBHOOK_SECRET (32–256 URL-safe chars) and WORKER_URL');
const url=new URL('/telegram/webhook',WORKER_URL);if(url.protocol!=='https:')throw new Error('HTTPS required');
const api=async(method,data)=>{const r=await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/${method}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const j=await r.json();if(!j.ok)throw new Error(`Telegram ${method}: ${j.error_code}`);return j.result;};
await api('setWebhook',{url:url.href,secret_token:WEBHOOK_SECRET,allowed_updates:['message','callback_query','chat_member','my_chat_member','channel_post'],max_connections:1,drop_pending_updates:false});
const info=await api('getWebhookInfo',{});console.log(JSON.stringify({url:info.url,pending:info.pending_update_count,allowed_updates:info.allowed_updates,last_error:info.last_error_message||null},null,2));
