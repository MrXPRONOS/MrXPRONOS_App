// Reject active content protocols even when HTML attributes are escaped.
export function isSafeCmsUrl(input,kind="link",baseUrl="https://mrxpronos.github.io/MrXPRONOS_App/") {
  const value=String(input??"").trim();
  if (!value || /[\u0000-\u001f\u007f]/u.test(value) || value.includes("\\") || value.startsWith("//")) return false;
  if(kind==="link" && value.startsWith("#")) return true;
  try {
    const parsed=new URL(value,baseUrl);
    if(kind==="link" && ["mailto:","tel:"].includes(parsed.protocol)) return true;
    if(!["http:","https:"].includes(parsed.protocol) || parsed.username || parsed.password) return false;
    return true;
  } catch {return false;}
}
export function safeCmsUrl(input,kind="link",fallback="#",baseUrl="https://mrxpronos.github.io/MrXPRONOS_App/") {
  return isSafeCmsUrl(input,kind,baseUrl)?String(input).trim():fallback;
}
