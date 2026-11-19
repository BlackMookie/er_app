from playwright.sync_api import sync_playwright
from pathlib import Path
r=Path('/mnt/data/er_v15_map_fix/Ethereal-Realms-Client-Serveur-v15.1-Map/client')
html=(r/'index.html').read_text()
html=html.replace('<link rel="stylesheet" href="/map.css">','<style>'+(r/'map.css').read_text()+'</style>')
html=html.replace('<script src="/map.js"></script>','<script>'+(r/'map.js').read_text()+'</script>')
atlas=(r/'eardan-atlas.html').read_text()
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1920,'height':1080})
 errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content(html,wait_until='domcontentloaded',timeout=30000)
 page.evaluate("document.querySelector('#table').hidden=false; document.querySelector('#navigation').hidden=false; document.querySelector('#er-cloud-gate').hidden=true; setView('map')")
 page.locator('#eardan-map iframe').evaluate('(el,html)=>{el.removeAttribute("src");el.srcdoc=html}',atlas)
 frame=page.frame_locator('#eardan-map iframe')
 frame.locator('#in').wait_for(timeout=20000)
 frame.locator('#in').click()
 zoom=frame.locator('#zoomValue').inner_text()
 frame.locator('#search').fill('Nescya')
 text=frame.locator('#results').inner_text()
 page.screenshot(path='/mnt/data/er_v15_map_fix/eardan-v15.1-map-test.png')
 print('zoom=',zoom,'search=',repr(text[:100]))
 print('visible',page.locator('#eardan-map').is_visible(),'tab',page.locator('#view-label').inner_text())
 page.evaluate("setView('craft')")
 print('map-hidden',not page.locator('#eardan-map').is_visible(), 'craft-visible',page.locator('[data-panel="craft"]').is_visible())
 page.evaluate("setView('map')")
 print('reopen',page.locator('#eardan-map').is_visible(),'errors',errors)
 assert not errors,errors
 assert text.strip(),'Search should find Nescya'
 assert zoom!='1×'
 browser.close()
