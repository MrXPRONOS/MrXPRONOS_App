import { chromium } from 'playwright';
import { icons } from 'lucide';
import { mkdir } from 'node:fs/promises';

const icon = icons.TrendingUp;
if (!icon) throw new Error('Lucide TrendingUp missing');
const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#35e4a0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
  icon.map(([tag, attrs]) => '<' + tag + ' ' + Object.entries(attrs).map(([k,v]) => k + '="' + v + '"').join(' ') + '/>').join('') + '</svg>';
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
  await page.setContent('<html><body style="margin:0;background:linear-gradient(145deg,#061326,#143b69);color:white;font:700 64px Arial;padding:90px"><h1>Mr XPRONOS</h1><p>Lucide + Playwright</p>'+svg+'</body></html>');
  await mkdir('crypto/generated',{recursive:true});
  await page.screenshot({path:'crypto/generated/design-tools-check.png',fullPage:false});
  console.log('DESIGN_TOOLS_OK: Lucide SVG + Playwright Chromium PNG');
} finally { await browser.close(); }
