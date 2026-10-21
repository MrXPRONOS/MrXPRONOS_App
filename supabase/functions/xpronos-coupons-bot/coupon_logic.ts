/** Calcul strict : pas d'arrondi avant le contrôle du seuil 4.00. */
export type Selection = { match: string; market: string; odds: string };
export function calculateCoupon(items: Selection[]): { total: string; selections: Selection[] } {
  if (items.length < 1 || items.length > 10) throw new Error('Entre 1 et 10 sélections.');
  let numerator = 1n;
  let denominator = 1n;
  const clean = items.map((s) => {
    const match = s.match.trim();
    const market = s.market.trim();
    const value = s.odds.trim();
    if (!match || !market || match.length > 120 || market.length > 120 || !/^\d{1,3}(\.\d{1,4})?$/.test(value)) {
      throw new Error('Sélection invalide. Format : Match ; Marché ; Cote (ex. 1.75).');
    }
    const [integer, decimals = ''] = value.split('.');
    const scaled = BigInt(integer) * 10000n + BigInt(decimals.padEnd(4, '0'));
    if (scaled <= 10000n || scaled > 1000000n) throw new Error('Cote individuelle hors limites (1.0001 à 100).');
    numerator *= scaled;
    denominator *= 10000n;
    return { match, market, odds: value };
  });
  if (numerator < 4n * denominator) throw new Error('Cote totale inférieure à 4.00. Coupon refusé.');
  const cents = (numerator * 100n + denominator / 2n) / denominator;
  return { total: `${cents / 100n}.${String(cents % 100n).padStart(2, '0')}`, selections: clean };
}

export function parseCouponCommand(raw: string) {
  const bits = raw.trim().split('|').map((x) => x.trim());
  if (bits.length < 6) throw new Error('Format : /addcoupon PRO | 50 | 2026-12-01T18:00 | -1 | Titre | Match ; Marché ; 1.70 | ...');
  const [tier, cost, expires, stock, title, ...bets] = bits;
  if (!['SIMPLE', 'PRO', 'VIP'].includes(tier.toUpperCase())) throw new Error('Catégorie SIMPLE, PRO ou VIP obligatoire.');
  if (!/^\d{1,6}$/.test(cost) || Number(cost) > 100000) throw new Error('Prix XP invalide.');
  if (!/^-?\d{1,6}$/.test(stock) || Number(stock) < -1 || Number(stock) > 100000) throw new Error('Stock invalide (-1 = illimité).');
  if (!title || title.length > 120) throw new Error('Titre invalide.');
  const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/.test(expires) ? expires : `${expires}Z`;
  const date = new Date(timestamp);
  if (!Number.isFinite(date.getTime()) || date.getTime() <= Date.now()) throw new Error('Date UTC future invalide.');
  const entries = bets.map((bit) => {
    const parts = bit.split(';').map((x) => x.trim());
    if (parts.length !== 3) throw new Error('Format sélection : Match ; Marché ; Cote.');
    return { match: parts[0], market: parts[1], odds: parts[2] };
  });
  const result = calculateCoupon(entries);
  return { tier: tier.toUpperCase(), xp_cost: Number(cost), expires_at: date.toISOString(), stock: Number(stock), title, selections: result.selections, total_odds: result.total };
}
