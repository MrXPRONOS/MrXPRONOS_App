/**
 * Libellés français des tickets Mr XPRONOS, alignés sur BSD V2 :
 * "Combiné", "Cote combinée", "Mise", "Gains potentiels", "Statut".
 * Ne change ni les identifiants, ni les cotes, ni la sélection du pari.
 */
export function categoryFrench(value) {
 const v=String(value||'Combiné').trim().toLocaleLowerCase('fr-FR');
 if(['akumulator','accumulator','accumulé','accumule','combiné','combine','combo'].includes(v))return 'Combiné';
 return String(value||'Combiné');
}
export function leagueFrench(value) {
 const raw=String(value||'Football · Ligue des champions de l’UEFA').trim();
 if(/^(?:sepak bola[.\s]*)?liga champions uefa$/i.test(raw))return 'Football · Ligue des champions de l’UEFA';
 return raw.replace(/^sepak bola[.\s]*/i,'Football · ');
}
export function statusFrench(value) {
 const v=String(value??'Prévision').trim();
 const lookup={
  diterima:'Accepté',accepted:'Accepté',accepté:'Accepté',
  pending:'À venir',awaiting:'À venir',scheduled:'À venir',upcoming:'À venir',
  forecast:'Prévision',prediction:'Prévision',prévision:'Prévision',predicted:'Prévision',
  won:'Réussi',win:'Réussi',lost:'Perdu',lose:'Perdu',
  settled:'Terminé',finished:'Terminé',completed:'Terminé',paid:'Payé'
 };
 return lookup[v.toLocaleLowerCase('fr-FR')]||v;
}
export function selectionFrench(raw, selectionKey='') {
 const text=String(raw||'Pronostic').trim();
 const key=String(selectionKey||'').trim().toUpperCase();
 if(key==='BTTS_YES')return 'Les deux équipes marquent : Oui';
 if(key==='BTTS_NO')return 'Les deux équipes marquent : Non';
 if(['1X','X2','12'].includes(key))return 'Double chance : '+key;
 if(['1','X','2'].includes(key))return 'Résultat du match : '+key;
 const totalKey=/^(OVER|UNDER)_(15|25|35|45)$/.exec(key);
 if(totalKey){
  return 'Total buts : '+(totalKey[1]==='OVER'?'plus de ':'moins de ')+totalKey[2][0]+','+totalKey[2][1];
 }
 if(/^1x2\s*\+\s*masing-masing\s+tim\s+mencetak/i.test(text)){
  return 'Résultat du match : 1 + Les deux équipes marquent : Oui';
 }
 if(/^peluang ganda\s*\+\s*kedua tim mencetak skor/i.test(text)){
  return 'Double chance : 1X + Les deux équipes marquent : Oui';
 }
 if(/^kedua tim mencetak skor[.:\s-]*(ya|yes|oui)$/i.test(text)){
  return 'Les deux équipes marquent : Oui';
 }
 const chance=/^double chance[.:\s-]*(1X|X2|12)$/i.exec(text);
 if(chance)return 'Double chance : '+chance[1].toUpperCase();
 const result=/^1x2[.:\s-]*M([12])$/i.exec(text);
 if(result)return 'Résultat du match : '+result[1];
 const total=/^total\s*\((\d+(?:[.,]\d+)?)\)\s*(over|under)$/i.exec(text);
 if(total)return 'Total buts : '+(total[2].toLowerCase()==='over'?'plus de ':'moins de ')+total[1].replace('.',',');
 return text;
}
