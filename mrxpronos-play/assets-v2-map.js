// Bibliothèque d’URLs des nouvelles ressources : intégrer après publication des fichiers.
// Le préfixe est relatif à mrxpronos-play/ dans la Mini App.
export const assetRoot = './assets/';
export const rankBadges = Object.freeze({
  1:'09-rank-badges/61-recrue-badge.webp',
  2:'09-rank-badges/62-eclaireur-badge.webp',
  3:'09-rank-badges/63-combattant-badge.webp',
  4:'09-rank-badges/64-sentinelle-badge.webp',
  5:'09-rank-badges/65-chevalier-badge.webp',
  6:'09-rank-badges/66-elite-badge.webp',
  7:'09-rank-badges/67-maitre-badge.webp',
  8:'09-rank-badges/68-champion-badge.webp',
  9:'09-rank-badges/69-legende-badge.webp',
  10:'09-rank-badges/70-mythique-badge.webp',
  11:'09-rank-badges/71-souverain-mx-badge.webp'
});
export const shopIcons = Object.freeze({
  'tap-110':'10-shop-boosts/72-boost-decouverte-110.webp',
  'tap-120':'10-shop-boosts/73-boost-guerrier-120.webp',
  'tap-150':'10-shop-boosts/74-boost-champion-150.webp',
  'tap-200':'10-shop-boosts/75-boost-souverain-200.webp',
  'energy-100':'11-progression-vfx/76-energy-recharge-100.webp',
  'energy-250':'11-progression-vfx/77-energy-recharge-250.webp'
});
export const progressIcons=Object.freeze({star:'11-progression-vfx/78-prestige-star.webp',ring:'11-progression-vfx/79-xp-progress-ring.webp',mastery:'11-progression-vfx/80-mastery-seal.webp',halo:'11-progression-vfx/81-rank-up-halo.webp',xpBurst:'11-progression-vfx/82-xp-spark-burst.webp',rankUp:'11-progression-vfx/83-rank-up-emblem.webp'});
export function assetUrl(path){return new URL(assetRoot+path,import.meta.url).href;}
