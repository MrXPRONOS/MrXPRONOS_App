// Telegram Bot API 10.3: rich message with media and in-message button rows.
// Revert to legacy sendPhoto/sendMessage ONLY on explicit 400/404 rejection.
// Network failures are not retried through a different endpoint to avoid duplicates.

export type InlineBtn={ text:string; url:string; style?:string };
export type InlineRow=InlineBtn[];

export function richBody(text:string, rows:InlineRow[], hasPhoto:boolean){
  const escapeHtml=(s:string)=>String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const image=hasPhoto?'<img src="tg://photo?id=coupon"/>':"";
  const desc=text?'<p>'+escapeHtml(text).replace(/\r?\n/g,"<br/>")+'</p>':"";
  const buttons=rows.map((row)=>{
    const nodes=row.filter(b=>b?.url&&/^https?:\/\//.test(b.url)).map(b=>{
      const style=["primary","success","danger"].includes(b.style||"")?b.style:"primary";
      return '<tg-button type="url" style="'+style+'" url="'+escapeHtml(b.url)+'">'+escapeHtml(b.text)+'</tg-button>';
    });
    return nodes.length?'<tg-button-row align="center">'+nodes.join("")+'</tg-button-row>':"";
  }).filter(Boolean).join("\n");
  return image+desc+buttons;
}

export function richPhotoPayload(text:string,rows:InlineRow[]){
  return {html:richBody(text,rows,true),
          media:[{id:"coupon",media:{type:"photo",media:"attach://coupon_photo"}}]};
}

export async function richPhotoOrLegacy(botToken:string,chatId:string,
    bytes:Uint8Array,caption:string,rows:InlineRow[],legacy:FormData,filename="coupon.png"){
  const rich=new FormData();
  rich.append("chat_id",chatId);
  rich.append("rich_message",JSON.stringify(richPhotoPayload(caption,rows)));
  rich.append("coupon_photo",new Blob([bytes],{type:"image/png"}),filename);
  const result=await fetch("https://api.telegram.org/bot"+botToken+"/sendRichMessage",
      {method:"POST",body:rich});
  if(result.status===400||result.status===404){
    console.warn("TELEGRAM_RICH_REJECTED",result.status,"legacy photo fallback");
    return fetch("https://api.telegram.org/bot"+botToken+"/sendPhoto",
       {method:"POST",body:legacy});
  }
  return result;
}

export async function richTextOrLegacy(botToken:string,chatId:string,
    text:string,rows:InlineRow[],legacy:FormData){
  const rich=new FormData();
  rich.append("chat_id",chatId);
  rich.append("rich_message",JSON.stringify({html:richBody(text,rows,false)}));
  const response=await fetch("https://api.telegram.org/bot"+botToken+"/sendRichMessage",
      {method:"POST",body:rich});
  if(response.status===400||response.status===404){
    console.warn("TELEGRAM_RICH_REJECTED",response.status,"legacy text fallback");
    return fetch("https://api.telegram.org/bot"+botToken+"/sendMessage",
        {method:"POST",body:legacy});
  }
  return response;
}
