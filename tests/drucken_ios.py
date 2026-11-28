"""Backlog V (Stefan, 28.11.2026): Drucken auf iPad und iPhone. Seit Backlog W bauen Einzelblatt, Blattsammlung, Heft und Lösungsheft
auf iPad/iPhone ein PDF (Test pdf_ios.py); hier bleibt: Hinweise, Knopftexte, Bericht teilt weiter eine HTML-Datei.
- Am Computer: kein Hinweiskasten, Knöpfe heißen „Drucken“ usw.
- iPad/iPhone in Safari: Hinweiskasten am Druck-Knopf („Erlauben“, Kopf-/Fußzeile, Skalierung, Computer); Knöpfe bleiben „Drucken“.
- App vom Home-Bildschirm: Knöpfe heißen „Teilen und drucken“, „Heft teilen und drucken“ …; ein Tipp gibt das Dokument als HTML-Datei
  an das Teilen-Menü (navigator.share); geht Teilen nicht, kommt ein Hinweis auf „Als Datei speichern“.
iPad/iPhone werden mit window.STUFENWEISE_IOS = 'safari' | 'app' nachgestellt, das Teilen-Menü mit einer Attrappe."""
import asyncio
from common import URL, launch
from playwright.async_api import async_playwright

ERR = []
def check(name, ok, info=''):
    print(('ok  ' if ok else 'ERR ') + f'[{name}] {info}')
    if not ok: ERR.append(name)

SHARE = """window.__shared = []; window.__canShare = true;
navigator.canShare = (d) => window.__canShare && !!d.files;
navigator.share = async (d) => { const f = d.files[0]; window.__shared.push({keys: Object.keys(d).sort().join(','), name: f.name, type: f.type, size: f.size, head: (await f.text()).slice(0, 15)}); };"""
SEED = "data.profiles.push({id:'k1',name:'Mia'}); data.current='k1'; saveData();"

async def page(br, mode):
    ctx = await br.new_context(viewport={'width': 1180, 'height': 900})
    if mode: await ctx.add_init_script(f"window.STUFENWEISE_IOS = '{mode}';" + SHARE)
    pg = await ctx.new_page(); pg.on('pageerror', lambda e: (ERR.append('pageerror'), print('ERR [pageerror]', e)))
    await pg.goto(URL); await pg.wait_for_timeout(500)
    return ctx, pg

async def sheet(pg, mode):
    await pg.evaluate(f"app.sheetMode = '{mode}'; openSheets('none'); app.sheetMode = '{mode}'; renderSheets()"); await pg.wait_for_timeout(700)

async def main():
    async with async_playwright() as p:
        br = await launch(p)
        # Computer
        ctx, pg = await page(br, None)
        await sheet(pg, 'single')
        check('Computer: kein Hinweiskasten', await pg.locator('.print-ios').count() == 0)
        check('Computer: Knopf „Drucken“', (await pg.inner_text('#sh-print')).strip() == 'Drucken')
        await ctx.close()
        # Safari auf dem iPad
        ctx, pg = await page(br, 'safari')
        await sheet(pg, 'single')
        t = await pg.inner_text('.print-ios') if await pg.locator('.print-ios').count() else ''
        check('Safari: kurzer PDF-Hinweis am Blatt', 'PDF' in t and 'Kopf- und Fußzeile' in t and '100 %' in t, t[:160])
        check('Safari: Knopf „Drucken (PDF)“', (await pg.inner_text('#sh-print')).strip() == 'Drucken (PDF)')
        await ctx.close()
        # App vom Home-Bildschirm
        ctx, pg = await page(br, 'app')
        await pg.evaluate(SEED)
        await sheet(pg, 'single')
        check('App: Knopf „Drucken (PDF)“', (await pg.inner_text('#sh-print')).strip() == 'Drucken (PDF)')
        await pg.click('#sh-samml'); await pg.wait_for_timeout(300)
        await sheet(pg, 'samml')
        check('App: „Alle drucken (PDF)“', (await pg.inner_text('#sm-print')).strip() == 'Alle drucken (PDF)')
        await pg.evaluate("app.sheetMode = 'heft'; renderSheets()"); await pg.wait_for_timeout(400)
        check('App: „Heft drucken (PDF)“', (await pg.inner_text('#hf-print')).strip() == 'Heft drucken (PDF)')
        # Bericht
        await pg.evaluate("window.__canShare = true; document.querySelectorAll('dialog[open]').forEach(d => d.close()); openReport('k1')"); await pg.wait_for_timeout(500)
        t = await pg.inner_text('#dlg-report .print-ios')
        check('App: Bericht weiter „Teilen und drucken“ mit bisherigem Hinweis', (await pg.inner_text('#rp-print')).strip() == 'Teilen und drucken' and 'Als Datei speichern' in t, t[:100])
        await pg.click('#rp-print'); await pg.wait_for_timeout(400)
        sh = await pg.evaluate("window.__shared")
        check('App: Bericht als HTML-Datei geteilt, nur die Datei', len(sh) == 1 and sh[0]['type'] == 'text/html' and sh[0]['keys'] == 'files', sh)
        await ctx.close(); await br.close()
    print('FEHLER' if ERR else 'alles ok', ERR)

asyncio.run(main())
