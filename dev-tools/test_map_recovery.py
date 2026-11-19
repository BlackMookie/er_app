import os,subprocess,time,urllib.request,uuid,json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path('/mnt/data/er_v15_map_fix/Ethereal-Realms-Client-Serveur-v15.1-Map')
env=dict(os.environ,ER_DB_PATH='/mnt/data/er_v15_map_fix/test_map.sqlite3')
p=subprocess.Popen([sys.executable,str(root/'server.py'),'--host','127.0.0.1','--port','18876'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env)
try:
 for i in range(50):
  try:
   r=urllib.request.urlopen('http://127.0.0.1:18876/map.js',timeout=1)
   if r.status==200: break
  except Exception:time.sleep(.1)
 else:raise RuntimeError('server failed')
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1920,'height':1080})
  failures=[]
  page.on('pageerror',lambda e:failures.append(str(e)))
  page.goto('http://127.0.0.1:18876/',wait_until='domcontentloaded',timeout=30000)
  page.wait_for_selector('#er-cloud-register-tab',state='visible',timeout=20000)
  page.click('#er-cloud-register-tab')
  name='testmap'+uuid.uuid4().hex[:8]
  page.fill('#er-cloud-username',name)
  page.fill('#er-cloud-password','SecureTestPassword!123')
  page.locator('#er-cloud-auth-submit').click()
  page.wait_for_function("!document.querySelector('#table').hidden && !document.querySelector('#local-map-tab').hidden",timeout=30000)
  page.locator('#local-map-tab').click()
  page.wait_for_function("!document.querySelector('#eardan-map').hidden && document.querySelector('#eardan-map iframe')?.contentDocument?.querySelector('#zoomValue')",timeout=30000)
  frame=page.frame_locator('#eardan-map iframe')
  frame.locator('#in').click()
  zoom=frame.locator('#zoomValue').inner_text()
  frame.locator('#search').fill('Nescya')
  page.screenshot(path='/mnt/data/er_v15_map_fix/eardan-v15.1-map-test.png',full_page=False)
  print('active tab=',page.locator('#view-label').inner_text(),'zoom=',zoom,'search=',frame.locator('#results').inner_text()[:200])
  print('map-visible=',page.locator('#eardan-map').is_visible(),'error=',failures)
  page.locator('[data-view="craft"]').click()
  print('craft-visible=',page.locator('[data-panel="craft"]').is_visible(),'map-hidden=',not page.locator('#eardan-map').is_visible())
  page.locator('#local-map-tab').click()
  print('map-reopen=',page.locator('#eardan-map').is_visible())
  assert not failures
  assert '1.5' in zoom
  assert page.locator('#eardan-map').is_visible()
  browser.close()
finally:
 p.terminate()
 try:p.wait(timeout=3)
 except:p.kill()
