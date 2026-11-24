/** Public Actu Foot news from the already deployed static news snapshot.
 * No Neon SDK, auth token, cross-site database credentials, or private URL.
 */
export async function loadFootNews() {
  const response=await fetch("./footnews.json",{cache:"no-store",headers:{Accept:"application/json"}});
  if(!response.ok)throw new Error("Actualités football momentanément indisponibles");
  const news=await response.json();
  if(!Array.isArray(news))throw new Error("Format actualités football invalide");
  return news;
}
// Compatibility with the former public-module import; this never contacts Neon.
export const loadNeonFootNews=loadFootNews;
