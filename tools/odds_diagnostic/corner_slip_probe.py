"""Public UI corner-total quote inspection. Never submits a wager."""
import re
ODD=re.compile(r"(?<!\d)(?:[1-9]\d?|[1-9])\.\d{2,3}(?!\d)")
CORNER=re.compile(r"corners?|corner kicks?|corners totaux|total.*corners",re.I)
CHOICE=re.compile(r"(over|under|plus de|moins de|supérieur|inférieur)\s*\d{1,2}[.,]5?",re.I)
async def inspect_corner_selection(page):
    result={"corner_label_clicked":False,"market_opened":False,"selection_clicked":False,"quote_observed":False,
            "visible_selection":None,"displayed_odds":None,"stage":"not_found"}
    # First inspect visible text, no account/login/bet submission.
    labels=page.get_by_text(CORNER)
    count=min(await labels.count(),25)
    for i in range(count):
        node=labels.nth(i)
        try:
            if await node.is_visible(timeout=700):
                await node.click(timeout=1500)
                result["corner_label_clicked"]=True
                result["stage"]="corner_label_clicked_not_verified"
                break
        except Exception:pass
    if not result["corner_label_clicked"]:return result
    await page.wait_for_timeout(900)
    options=page.get_by_text(CHOICE)
    for i in range(min(await options.count(),35)):
        node=options.nth(i)
        try:
            if not await node.is_visible(timeout=700):continue
            txt=(await node.inner_text(timeout=800)).strip()[:80]
            # Only click a selection, never any button that places or confirms a bet.
            if re.search(r"place bet|parier|confirmer|bet now|valider|deposit|déposer",txt,re.I):continue
            context=(await node.locator("xpath=..").inner_text(timeout=900))[:350]
            odds=ODD.findall(context)
            result["market_opened"]=True
            result["visible_selection"]=txt
            if odds:
                result["displayed_odds"]=odds[0]
                result["quote_observed"]=True
            await node.click(timeout=1400)
            result["selection_clicked"]=True
            result["stage"]="selection_added_to_slip_no_submission"
            await page.wait_for_timeout(650)
            break
        except Exception:continue
    if not result["selection_clicked"]:result["stage"]="corner_label_without_verified_total_selection"
    return result
