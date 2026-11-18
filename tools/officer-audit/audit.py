#!/usr/bin/env python3
"""Click through Ora's officer shifts at 1280x800 and 390x844 (night map off and on), screenshot each
moment, time a day file, and report console errors. Needs the local server on :8934.
    uv run --no-project --with playwright python tools/officer-audit/audit.py OUTDIR"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
URL = "http://localhost:8934/#c=-87.68,41.87&z=10.6"
errors, report = [], {}
# pins: image off-n-K for the K-th ticket in time order of the tickets shown (all, or the picked type)
PINS = """() => { const f=map.getSource('off-pts')._data.features, tk=offTk(), pos=new Map(tk.map((t,i)=>[t.n,i+1]));
  const timesUp=tk.every((t,i)=>i===0||tk[i-1].time<=t.time);
  return f.length>0 && timesUp && f.every(x=>x.properties.img.replace(/^off-n-|-l$/g,'')===String(pos.get(x.properties.n))); }"""
# nothing in the officer UI is cut off or sticks out of its box
CUT = """() => { const out=[]; for(const root of document.querySelectorAll('#offSec,#offCard,#offListSheet,#offCardSheet')){
  const R=root.getBoundingClientRect(); if(!R.width||getComputedStyle(root).display==='none') continue;
  for(const e of root.querySelectorAll('*')){ const r=e.getBoundingClientRect(), c=getComputedStyle(e); if(!r.width||c.display==='none') continue;
    if(!e.closest('.off-tl,.off-list,.filters') && (r.right>R.right+1||r.left<R.left-1)) out.push('sticks out: '+(e.className||e.tagName));
    if(!e.children.length && e.scrollWidth>e.clientWidth+1 && /hidden|clip/.test(c.overflow+c.overflowX)) out.push('cut: '+(e.innerText||'').slice(0,30)); } }
  return out; }"""

async def st(page):
    return await page.evaluate("() => ({sel:OFF.sel, mode:OFF.mode, day:OFF.day, show:OFF.show, hl:OFF.hl, lh:OFF.lh, oh:OFF.oh, tk:OFF.tk.length, markers:document.querySelectorAll('.off-mav').length})")

async def shot(page, name):
    await page.wait_for_timeout(900); await page.screenshot(path=f"{OUT}/{name}.png"); print(name, json.dumps(await st(page)))

async def desktop(b, night):
    ctx = await b.new_context(viewport={"width": 1280, "height": 800}); page = await ctx.new_page()
    page.on("console", lambda m: m.type == "error" and errors.append(f"desk{'-night' if night else ''}: " + m.text[:200]))
    page.on("pageerror", lambda e: errors.append("desk: " + str(e)[:200]))
    await page.add_init_script(f"localStorage.setItem('ora-night','{'dark' if night else 'light'}')")
    await page.goto(URL); await page.wait_for_function("typeof map!=='undefined' && map.loaded()", timeout=60000); await page.wait_for_timeout(1500)
    tag = "n" if night else "d"
    await page.click("#obtn"); await shot(page, f"{tag}01-intro"); await page.click("#offIntroGo"); await shot(page, f"{tag}02-list")
    await page.locator("#offSec .off-row").nth(3).click(); await page.wait_for_timeout(700); await shot(page, f"{tag}03-picked")
    ms = await page.evaluate("async () => { const k=OFF.day; offDayCache.delete(k); const t=performance.now(); await offGet(`chicago-officers/days/${k}.json`, offDayCache, k); return Math.round(performance.now()-t); }")
    report[f"{tag} day file ms"] = ms
    # the day tiles must match the tickets listed (an officer can work two shifts on one date)
    report[f"{tag} day tiles equal tickets listed"] = await page.evaluate("() => document.querySelector('#offCard .enf-stat .num').textContent.replace(/,/g,'')==String(OFF.tk.length)")
    await page.click("[data-off-show]"); await shot(page, f"{tag}04-route")
    # every pin carries its number, counting 1, 2, 3 in the order the officer wrote the tickets
    report[f"{tag} route pins numbered in time order"] = await page.evaluate(PINS)
    await page.locator("#offCard .off-tr").nth(2).click(); await shot(page, f"{tag}05-ticket")
    prev = await page.evaluate("() => { const m=[...new Set(OFF.shifts[OFF.sel].map(s=>s[0]))]; return [...m].reverse().find(d=>d<OFF.day)||null; }")
    await page.locator("#offCard [data-off-jump]").first.click(); await page.wait_for_timeout(900)
    report[f"{tag} Previous shift link went to the previous shift"] = (await st(page))["day"] == prev
    # every officer-day on the last day: tiles equal tickets in the day file
    report[f"{tag} all officers tie out on the last day"] = await page.evaluate("async () => { const d=await offGet(`chicago-officers/days/${OFF.last}.json`, offDayCache, OFF.last); const by={}; d.forEach(t=>by[t[0]]=(by[t[0]]||0)+1); return Object.entries(by).every(([id,n])=>offShiftOn(+id,OFF.last)[1]===n); }")
    await page.click("[data-off-mode=range]"); await page.wait_for_timeout(700); await shot(page, f"{tag}06-range")
    ok = await page.evaluate("() => { const ds=new Set(offDates()); const sh=OFF.shifts[OFF.sel].filter(s=>ds.has(s[0])); const n=sh.reduce((a,s)=>a+s[1],0); return document.querySelector('#offCard .enf-stat .num').textContent.replace(/,/g,'')==String(n); }")
    report[f"{tag} range total equals its days"] = ok
    await page.click("[data-off-show]"); await shot(page, f"{tag}07-dots")
    # ticket type: the list ranks by that type and its numbers come from types.json; the card matches its tickets
    await page.click("[data-off-mode=day]"); await page.wait_for_timeout(700)
    top = await page.evaluate("() => OFF.typeOrder[0]")
    await page.click("#offSec [data-off-filter]"); await page.wait_for_timeout(300)
    await page.select_option("#offSec [data-off-type]", top); await page.wait_for_timeout(1200); await shot(page, f"{tag}09-type")
    report[f"{tag} type list ranked and tied to types.json"] = await page.evaluate("() => { const R=offRows(); const ok=R.every((r,i)=>i===0||R[i-1].f>=r.f); const tie=R.every(r=>{ const v=((OFF.types[r.o.id]||{})[OFF.day]||{})[OFF.type]; return v && v[0]===r.n; }); return ok && tie && R.length>0; }")
    await page.locator("#offSec .off-row").nth(0).click(); await page.wait_for_timeout(1400); await shot(page, f"{tag}10-type-card")
    await page.click("#offCard [data-off-show]"); await page.wait_for_timeout(1200)
    report[f"{tag} type pins count 1, 2, 3"] = await page.evaluate(PINS)
    report[f"{tag} type card equals its tickets"] = await page.evaluate("() => document.querySelector('#offCard .enf-stat .num').textContent.replace(/,/g,'')==String(offTk().length) && offTk().every(t=>String(t.v)===OFF.type)")
    await page.click("#offSec [data-off-rank=tickets]"); await page.wait_for_timeout(600)
    report[f"{tag} rank by tickets"] = await page.evaluate("() => { const R=offRows(); return R.every((r,i)=>i===0||R[i-1].n>=r.n); }")
    report[f"{tag} nothing cut off"] = await page.evaluate(CUT)
    await page.keyboard.press("Escape"); await shot(page, f"{tag}08-escape")
    await ctx.close()

async def phone(b):
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = await ctx.new_page(); cdp = await ctx.new_cdp_session(page)
    page.on("console", lambda m: m.type == "error" and errors.append("phone: " + m.text[:200]))
    async def drag(sel, y1):
        box = await page.locator(sel).bounding_box(); y0 = box["y"] + 10
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 195, "y": y0}]})
        for k in range(1, 13):
            await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 195, "y": y0 + (y1 - y0) * k / 12}]}); await page.wait_for_timeout(16)
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await page.add_init_script("localStorage.setItem('ora-officer-intro','1')")
    await page.goto(URL); await page.wait_for_function("typeof map!=='undefined' && map.loaded()", timeout=60000); await page.wait_for_timeout(1500)
    await page.tap("#obtn"); await shot(page, "p01-list")
    report["phone search bar inside the header card"] = await page.evaluate("() => document.querySelector('#search').getBoundingClientRect().bottom <= document.getElementById('panel').getBoundingClientRect().bottom-8")
    await drag("#offListSheet .off-shead", 120); await shot(page, "p02-list-90")
    report["phone full sheet stops under the header card"] = await page.evaluate("() => document.getElementById('offListSheet').getBoundingClientRect().top >= document.getElementById('panel').getBoundingClientRect().bottom")
    await drag("#offListSheet .off-shead", 480); await shot(page, "p03-list-50")
    await page.locator("#offLsBody .off-row").nth(2).tap(); await page.wait_for_timeout(700); await shot(page, "p04-picked")
    await page.tap("#offCardSheet [data-off-show]"); await shot(page, "p05-route")
    await drag("#offCardSheet .off-shead", 100); await shot(page, "p06-card-90")
    await page.locator("#offCardSheet .off-tr").nth(1).tap(); await shot(page, "p07-ticket")
    report["phone tapped ticket shows in the bar"] = await page.evaluate("() => { const b=document.querySelector('#offCardSheet .off-selbar .off-tn'); return !!b && b.textContent===String(offLabels().get(OFF.hl)); }")
    report["phone popup clear of the header card"] = await page.evaluate("() => { const p=document.querySelector('.maplibregl-popup'); return !p || p.getBoundingClientRect().top >= document.getElementById('panel').getBoundingClientRect().bottom; }")
    report["phone nothing cut off"] = await page.evaluate(CUT)
    small = await page.evaluate("() => [...document.querySelectorAll('#obtn,.off-x,.off-step button,.color-btn,.fchip,.off-fbtn,.off-chip,.off-type')].filter(e=>e.offsetParent).map(e=>e.getBoundingClientRect()).filter(r=>r.height<44||r.width<44).length")
    report["phone targets under 44px"] = small
    await page.tap("#offCardSheet [data-off-close]"); await shot(page, "p08-closed")
    await ctx.close()

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        await desktop(b, False); await desktop(b, True); await phone(b); await b.close()
    print(json.dumps(report, indent=1)); print("console errors:", len(errors)); [print(" ", e) for e in errors[:20]]
asyncio.run(main())
