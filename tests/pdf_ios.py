"""Backlog W (Stefan, 28.11.2026): Die App baut das PDF selbst (html2canvas + eigener PDF-Schreiber).
Für jede Ausgabeart: Seitenzahl wie beim Drucken in Chrome (page.pdf mit @page), Seitenformat (A4 hoch, Bogen A4 quer bzw. A3 quer),
Größe je Seite, Seite nicht leer. Dazu die Knöpfe: iPad/iPhone „Drucken (PDF)“ mit Fortschritt, Teilen nur mit der Datei;
Computer: „Drucken“ bleibt, Zusatzknopf „Als PDF“ lädt das PDF herunter."""
import asyncio, base64, re, subprocess, tempfile, os
from common import URL, launch
from playwright.async_api import async_playwright

ERR = []
def check(name, ok, info=''):
    print(('ok  ' if ok else 'ERR ') + f'[{name}] {info}')
    if not ok: ERR.append(name)

SHARE = """window.__shared = [];
navigator.canShare = (d) => !!d.files;
navigator.share = async (d) => { const f = d.files[0]; window.__shared.push({keys: Object.keys(d).sort().join(','), name: f.name, type: f.type, size: f.size}); };"""

def info(pdf):
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as t: t.write(pdf); fn = t.name
    out = subprocess.run(['pdfinfo', '-l', '9999', fn], capture_output=True, text=True).stdout
    sizes = [(round(float(w)*25.4/72), round(float(h)*25.4/72)) for w, h in re.findall(r'Page\s+\d+ size:\s+([\d.]+) x ([\d.]+)', out)]
    png = subprocess.run(['pdftoppm', '-r', '20', '-gray', '-f', '1', '-l', '1', fn], capture_output=True).stdout   # PGM: dunkelster Wert
    os.unlink(fn)
    return sizes, png

os.makedirs('pdf', exist_ok=True)   # tests/out/pdf: eigenes PDF und Chrome-Druck zum Vergleichen
async def chrome_pages(br, html, name=''):
    d = await br.new_page(); await d.set_content(html); await d.wait_for_timeout(700)
    pdf = await d.pdf(prefer_css_page_size=True, print_background=True); await d.close()
    if name: open(f'pdf/{name}_chrome.pdf', 'wb').write(pdf)
    return len(re.findall(rb'/Type\s*/Page[^s]', pdf))

async def own_pdf(pg, expr):
    b64 = await pg.evaluate("""async (expr) => { const html = eval(expr); const b = await pdfFromHtml(html);
      const u = new Uint8Array(await b.arrayBuffer()); let s = ''; for(let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); }""", expr)
    return base64.b64decode(b64)

async def case(br, pg, name, expr, fmt):
    html = await pg.evaluate(expr)
    fn = re.sub(r'\W+', '_', name)
    n0 = await chrome_pages(br, html, fn)
    pdf = await own_pdf(pg, expr)
    open(f'pdf/{fn}.pdf', 'wb').write(pdf)
    sizes, png = info(pdf)
    kb = len(pdf)/1024/max(1, len(sizes))
    check(f'{name}: {n0} Seiten wie beim Drucken', len(sizes) == n0, f'PDF {len(sizes)}, Chrome {n0}')
    check(f'{name}: Format {fmt[0]} × {fmt[1]} mm', sizes and all(abs(w - fmt[0]) <= 1 and abs(h - fmt[1]) <= 1 for w, h in sizes), sizes[:3])
    a4 = fmt[0]*fmt[1]/(210*297)
    check(f'{name}: höchstens 0,35 MB je A4-Fläche', kb < 360*a4, f'{kb:.0f} KB je Seite, {len(pdf)/1048576:.1f} MB')
    px = png.split(b'\n', 3)[-1] if png[:2] == b'P5' else b''
    check(f'{name}: Seite 1 nicht leer', px and min(px) < 120 and sum(1 for v in px if v < 200) > len(px)//200, f'{sum(1 for v in px if v < 200)} dunkle von {len(px)}')
    return len(sizes)

async def main():
    async with async_playwright() as p:
        br = await launch(p)
        ctx = await br.new_context(viewport={'width': 1180, 'height': 900}, accept_downloads=True)
        pg = await ctx.new_page(); pg.on('pageerror', lambda e: (ERR.append('pageerror'), print('ERR [pageerror]', e)))
        await pg.goto(URL); await pg.wait_for_timeout(500)
        await pg.evaluate("data.profiles.push({id:'k1', name:'Lea', created:1, updated:1, world:'HS'}); saveData(); app.sheet.sol = true; app.sheetMode = 'single'; openSheets('k1')")
        await pg.wait_for_timeout(800)
        # Einzelblätter
        await case(br, pg, 'Einzelblatt mit Lösung', "(() => { app.sheet.topic = 'M:plus'; app.sheet.zr = 20; app.sheet.gross = false; return buildSheet().html; })()", (210, 297))
        await case(br, pg, 'Basis groß mit Bastelseite', "(() => { app.sheet.topic = 'B:V6'; app.sheet.gross = true; app.sheet.bart = {V6: 2}; return buildSheet().html; })()", (210, 297))
        quer = await pg.evaluate("(() => { for(const k of ['strahl20','strahl100','zwanzig','zehner','geld','stellen']){ app.sheet.topic = 'K:' + k; app.sheet.gross = false; const d = buildSheet(); if(d.quer) return k; } return ''; })()")
        if quer: await case(br, pg, f'Legeblatt quer ({quer})', f"(() => {{ app.sheet.topic = 'K:{quer}'; return buildSheet().html; }})()", (210, 297))
        else: print('(kein Legeblatt quer gefunden)')
        # Blattsammlung
        await pg.evaluate("app.samml.items = []; saveSamml(); app.sheet.gross = false; app.sheet.topic = 'M:plus'; renderSheets()"); await pg.wait_for_timeout(1000)
        await pg.click('#sh-samml'); await pg.wait_for_timeout(200)
        await pg.evaluate("app.sheet.topic = 'L:L2'; app.sheet.sol = false; renderSheets()"); await pg.wait_for_timeout(1000)
        await pg.click('#sh-samml'); await pg.wait_for_timeout(200)
        await case(br, pg, 'Blattsammlung', "buildSamml().html", (210, 297))
        # Heft (Bereich, 12 Seiten)
        await pg.evaluate("app.sheetMode = 'heft'; app.heft = {title:'Probe', pid:'none', items:[], toc:true, weg:'bereich', pages:12}; saveHeft(); openSheets('none'); app.sheetMode = 'heft'; renderSheets()"); await pg.wait_for_timeout(600)
        await pg.click('[data-hfbfach="M"]'); await pg.wait_for_timeout(300)
        await pg.select_option('#hf-ber', 'M|20'); await pg.select_option('#hf-von', 'M|20|I'); await pg.select_option('#hf-bis', 'M|20|II')
        await pg.click('#hf-zone'); await pg.wait_for_function("app.heft.book && app.heft.items.length > 5", timeout=120000); await pg.wait_for_timeout(800)
        n = await case(br, pg, 'Heft A4', "(() => { app.heft.druck = 'a4'; return buildHeft().html; })()", (210, 297))
        check('Heft A4: 12 Seiten', n == 12, n)
        n = await case(br, pg, 'Broschüre A5 (A4 quer)', "(() => { app.heft.druck = 'a5'; return buildHeft().html; })()", (297, 210))
        check('Broschüre A5: 6 Bögen-Seiten (12 Heftseiten)', n == 6, n)
        await case(br, pg, 'Broschüre A4 (A3 quer)', "(() => { app.heft.druck = 'a3'; return buildHeft().html; })()", (420, 297))
        await pg.evaluate("app.heft.druck = 'a4'; saveHeft()")
        await case(br, pg, 'Lösungsheft', "buildLoesung().html", (210, 297))

        # Computer: Drucken bleibt, Zusatzknopf „Als PDF“ lädt herunter
        await pg.evaluate("app.sheetMode = 'single'; app.sheet.topic = 'M:plus'; app.sheet.sol = false; renderSheets()"); await pg.wait_for_timeout(1000)
        check('Computer: „Drucken“ und „Als PDF“', (await pg.inner_text('#sh-print')).strip() == 'Drucken' and (await pg.inner_text('#sh-pdf')).strip() == 'Als PDF' and await pg.locator('.print-ios').count() == 0)
        async with pg.expect_download(timeout=120000) as dl:
            await pg.click('#sh-pdf')
        d = await dl.value
        pdf = open(await d.path(), 'rb').read()
        check('Computer: PDF heruntergeladen', d.suggested_filename.endswith('.pdf') and pdf[:5] == b'%PDF-', d.suggested_filename)
        await pg.wait_for_selector('#pdf-dl'); await pg.click('#dlg-pdf [data-close]')
        check('Computer: Heft hat „Als PDF“', await pg.evaluate("app.sheetMode = 'heft'; renderSheets(); !!document.querySelector('#hf-pdf') && !!document.querySelector('#hf-sol-pdf')"))
        await ctx.close()

        # iPad/iPhone (Home-Bildschirm-App): „Drucken (PDF)“, Fortschritt, Teilen nur mit der Datei
        for mode in ('app', 'safari'):
            ctx = await br.new_context(viewport={'width': 1024, 'height': 768})
            await ctx.add_init_script(f"window.STUFENWEISE_IOS = '{mode}';" + SHARE)
            pg = await ctx.new_page(); pg.on('pageerror', lambda e: (ERR.append('pageerror'), print('ERR [pageerror]', e)))
            await pg.goto(URL); await pg.wait_for_timeout(500)
            await pg.evaluate("app.sheet.topic = 'M:plus'; app.sheet.zr = 20; app.sheet.sol = true; app.sheetMode = 'single'; openSheets('none')"); await pg.wait_for_timeout(1200)
            check(f'{mode}: Knopf „Drucken (PDF)“, kein Zusatzknopf', (await pg.inner_text('#sh-print')).strip() == 'Drucken (PDF)' and await pg.locator('#sh-pdf').count() == 0)
            t = await pg.inner_text('.print-ios')
            check(f'{mode}: kurzer Hinweis zum PDF', 'PDF' in t and '100 %' in t and 'Erlauben' not in t, t)
            await pg.click('#sh-print')
            await pg.wait_for_function("/Seite \\d+ von \\d+/.test(document.querySelector('#pdf-st')?.textContent || '') || !!document.querySelector('#pdf-share')", timeout=60000)
            st = await pg.evaluate("document.querySelector('#pdf-st')?.textContent || ''")
            check(f'{mode}: Fortschritt „Seite … von …“ mit Abbrechen', not st or ('von 2' in st and await pg.locator('#pdf-stop').count() == 1), st)
            await pg.wait_for_selector('#pdf-share', timeout=120000)
            await pg.click('#pdf-share'); await pg.wait_for_timeout(400)
            sh = await pg.evaluate("window.__shared")
            check(f'{mode}: Teilen nur mit der PDF-Datei', len(sh) == 1 and sh[0]['keys'] == 'files' and sh[0]['type'] == 'application/pdf' and sh[0]['name'].endswith('.pdf'), sh)
            await pg.click('#dlg-pdf [data-close]')
            if mode == 'app':
                # Abbrechen
                await pg.evaluate("app.sheetMode = 'heft'; app.heft = {title:'X', pid:'none', items:[], toc:true, weg:'bereich', pages:12}; renderSheets()")
                await pg.evaluate("setTimeout(() => pdfMake('Test', () => buildSheet().html), 0)")
                await pg.wait_for_selector('#pdf-stop'); await pg.click('#pdf-stop'); await pg.wait_for_timeout(1500)
                check(f'{mode}: Abbrechen schließt ohne Teilen', not await pg.evaluate("$('#dlg-pdf').open") and len(await pg.evaluate("window.__shared")) == 1)
            await ctx.close()
        await br.close()
    print('FEHLER' if ERR else 'alles ok', ERR)

asyncio.run(main())
