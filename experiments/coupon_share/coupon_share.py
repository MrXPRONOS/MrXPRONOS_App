"""Experimental 1win Share Bet UI adapter. No stake, login, or bet placement.
Live mode requires locally verified selectors and permission for automated use.
Run: python coupon_share.py --self-test (with Playwright + Chromium installed).
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def load_picks(source, ids, now=None):
    now = now or datetime.now(timezone.utc)
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Provide distinct match IDs explicitly')
    matches = source['matches']
    result = []
    for mid in ids:
        found = [m for m in matches if str(m.get('id')) == str(mid)]
        if len(found) != 1:
            raise ValueError(f'Missing or ambiguous match ID {mid}')
        m = found[0]
        start = datetime.fromisoformat(m['event_date'].replace('Z', '+00:00'))
        if start.tzinfo is None or start <= now or m.get('is_finished'):
            raise ValueError(f'Match {mid} is not a confirmed future event')
        pick = m['prediction']['double_chance']
        if pick not in ('1X', 'X2'):
            raise ValueError(f'Unsupported market {pick}')
        result.append({'id': str(mid), 'home': m['home_team'], 'away': m['away_team'],
                       'league': m['league'], 'start': start.isoformat(), 'pick': pick})
    return result


def one(locator):
    locator.first.wait_for(state='visible', timeout=8000)
    if locator.count() != 1:
        raise RuntimeError('Missing or ambiguous UI element')
    return locator




def match_row(page, selector, pick):
    rows = page.locator(selector)
    for field in ('home', 'away', 'league'):
        rows = rows.filter(has=page.get_by_text(pick[field], exact=True))
    # Exact kickoff is provided by a verified site-specific timestamp locator.
    rows = rows.filter(has=page.locator('[datetime]'))
    matching = []
    for row in rows.all():
        times = row.locator('[datetime]').all()
        for t in times:
            raw = t.get_attribute('datetime')
            try:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if dt.tzinfo and dt == datetime.fromisoformat(pick['start']):
                    matching.append(row)
                    break
            except (AttributeError, ValueError):
                continue
    if len(matching) != 1:
        raise RuntimeError(f'Cannot verify exact event {pick["id"]}')
    return matching[0]


def create_share(page, picks, cfg):
    if page.locator(cfg['slip_rows']).count():
        raise RuntimeError('Start with an empty slip')
    for pick in picks:
        row = match_row(page, cfg['event_rows'], pick)
        market = one(row.locator(cfg['double_chance_market']))
        one(market.get_by_role('button', name=pick['pick'], exact=True)).click()
    # Verify every item and the count before sharing; no submit/placement action.
    slip_rows = page.locator(cfg['slip_rows'])
    if slip_rows.count() != len(picks):
        raise RuntimeError('Slip count differs from requested selections')
    for pick in picks:
        row = match_row(page, cfg['slip_rows'], pick)
        one(row.get_by_text(pick['pick'], exact=True))
        one(row.get_by_text(cfg['market_label'], exact=True))
    one(page.get_by_role('button', name=cfg['share_label'], exact=True)).click()
    code_field = one(page.locator(cfg['code_field']))
    code = (code_field.input_value() if code_field.evaluate('(el) => el instanceof HTMLInputElement') else code_field.inner_text()).strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{4,128}', code):
        raise RuntimeError('No valid code in designated share-code field')
    return code


FIXTURE = '''<main><div class="event"><span>Alpha</span><span>Beta</span><span>Test League</span><time datetime="2099-01-01T12:00:00Z">Kickoff</time><div class="dc"><button id="pick">1X</button><button>X2</button></div></div><div id="slip"></div><button id="share">Share</button><input id="code" hidden></main><script>document.querySelector('#pick').onclick=()=>{document.querySelector('#slip').innerHTML='<div class="leg"><span>Alpha</span><span>Beta</span><span>Test League</span><time datetime="2099-01-01T12:00:00Z">Kickoff</time><span>Double Chance</span><span>1X</span></div>'};document.querySelector('#share').onclick=()=>{const e=document.querySelector('#code');e.hidden=false;e.value='TEST_ONLY_123';};</script>'''
FIXTURE_CFG = dict(event_rows='.event', double_chance_market='.dc', slip_rows='.leg', market_label='Double Chance', share_label='Share', code_field='#code')


def launch(p, headed=False):
    options = {'headless': not headed}
    if os.getenv('CHROMIUM_PATH'):
        options['executable_path'] = os.environ['CHROMIUM_PATH']
    return p.chromium.launch(**options)


def self_test():
    from playwright.sync_api import sync_playwright
    data = {'matches': [{'id': 1, 'event_date': '2099-01-01T12:00:00Z', 'home_team': 'Alpha', 'away_team': 'Beta', 'league': 'Test League', 'prediction': {'double_chance': '1X'}}]}
    picks = load_picks(data, ['1'])
    with sync_playwright() as p, launch(p) as browser:
        page = browser.new_page()
        page.set_content(FIXTURE)
        assert create_share(page, picks, FIXTURE_CFG) == 'TEST_ONLY_123'
        print('PASS: simulated UI creates and extracts mock share code')
        try:
            create_share(page, picks, FIXTURE_CFG)
        except RuntimeError:
            print('PASS: non-empty slip rejected')
        else:
            raise AssertionError('Non-empty slip accepted')
        page.set_content(FIXTURE)
        try:
            create_share(page, [dict(picks[0], away='Wrong')], FIXTURE_CFG)
        except RuntimeError:
            print('PASS: wrong match rejected')
        else:
            raise AssertionError('Wrong match accepted')
        page.set_content(FIXTURE.replace("TEST_ONLY_123", ""))
        try:
            create_share(page, picks, FIXTURE_CFG)
        except RuntimeError:
            print('PASS: missing code rejected')
        else:
            raise AssertionError('Missing code accepted')
    try:
        load_picks(data, ['1', '1'])
    except ValueError:
        print('PASS: duplicate match IDs rejected')
    else:
        raise AssertionError('Duplicate IDs accepted')
    try:
        load_picks(data, ['1'], datetime(2100, 1, 1, tzinfo=timezone.utc))
    except ValueError:
        print('PASS: started match rejected')
    else:
        raise AssertionError('Started match accepted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--data', default='data.json')
    parser.add_argument('--match-id', action='append')
    parser.add_argument('--config', help='Locally verified 1win UI selector JSON')
    parser.add_argument('--authorized', action='store_true', help='Confirm permitted automated use of this interface')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.authorized or not args.config or not args.match_id:
        parser.error('Live mode requires --authorized, --config and explicit --match-id')
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    url = urlparse(cfg['url'])
    if url.scheme != 'https' or url.hostname not in ('1win.com', 'www.1win.com') or url.username or url.password:
        parser.error('Only the explicitly allowed official 1win domain is supported')
    picks = load_picks(json.loads(Path(args.data).read_text(encoding='utf-8')), args.match_id)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p, launch(p, headed=True) as browser:
        page = browser.new_page()
        response = page.goto(cfg['url'], wait_until='domcontentloaded', timeout=30000)
        if response is None or response.status >= 400 or urlparse(page.url).hostname not in ('1win.com', 'www.1win.com'):
            raise RuntimeError('Site unavailable or redirected; stopping without retry')
        code = create_share(page, picks, cfg)
        print(json.dumps({'bookmaker': '1win', 'status': 'share_code_extracted_unverified', 'code': code, 'match_ids': args.match_id}))


if __name__ == '__main__':
    main()
