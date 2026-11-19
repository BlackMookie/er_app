from pathlib import Path
import shutil, zipfile, re
root=Path('/mnt/data/er_v15_map_fix')
base=root/'Ethereal-Realms-Client-Serveur-v15'
out=root/'Ethereal-Realms-Client-Serveur-v15.1-Map'
if out.exists(): shutil.rmtree(out)
shutil.copytree(base,out)
client=out/'client'
# Source atlas recovery from user Library - source, not fake reconstruction of absent map.js/css.
atlas=(root/'Eardan-Atlas.html').read_text(encoding='utf-8')
corrections={'Neseya':'Nescya','Hakkoshu':'Hakkeshu','Mustis':'Mushis','Fënis':'Fenris','Gacorens':'Gaorens','Bohkans':'Rohkans'}
for old,new in corrections.items():
 atlas=atlas.replace(old,new)
(client/'eardan-atlas.html').write_text(atlas,encoding='utf-8')
(client/'map.css').write_text('''/* Carte d’Eardan — récupération autonome depuis Eardan-Atlas. */
#eardan-map{display:block;margin:5px;min-width:0;}
#eardan-map[hidden]{display:none!important;}
#eardan-map .er-map-heading{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;gap:12px;background:#fffaf1;border:1px solid #dccbb2;border-radius:9px 9px 0 0;}
#eardan-map .er-map-heading h2{font:700 20px var(--er-fantasy-font,Georgia,serif);color:#533955;margin:0;}
#eardan-map .er-map-heading p{color:#75687b;font-size:11px;line-height:1.3;margin:0;}
#eardan-map iframe{display:block;width:100%;height:clamp(580px,calc(100dvh - 128px),1250px);border:1px solid #dccbb2;border-top:0;border-radius:0 0 9px 9px;background:#e4d5b7;}
@media(max-width:900px){#eardan-map iframe{height:calc(100dvh - 176px);min-height:470px}#eardan-map .er-map-heading{align-items:start;flex-direction:column}}
''',encoding='utf-8')
(client/'map.js').write_text('''/* Adaptateur Carte d’Eardan : atlas embarqué, sans dépendance externe. */
(()=>{'use strict';
const host=document.getElementById('table');
if(!host || document.getElementById('eardan-map'))return;
const page=document.createElement('section');page.id='eardan-map';page.hidden=true;
page.setAttribute('aria-label','Carte d’Eardan');
const heading=document.createElement('div');heading.className='er-map-heading';
const title=document.createElement('h2');title.textContent='Carte d’Eardan';
const desc=document.createElement('p');desc.textContent='Atlas · exploration et consultation';
heading.append(title,desc);
const iframe=document.createElement('iframe');iframe.title='Atlas interactif d’Eardan';
iframe.loading='lazy';iframe.setAttribute('allowfullscreen','');
page.append(heading,iframe);host.append(page);
let initialized=false,accountKey='';
window.eardanMap={
 account(key){accountKey=String(key||'');},
 show(){page.hidden=false;if(!initialized){iframe.src='/eardan-atlas.html';initialized=true;}},
 hide(){page.hidden=true;},
 get accountKey(){return accountKey;}
};
})();
''',encoding='utf-8')
html=(client/'index.html').read_text(encoding='utf-8')
needle="  if (mapVisible && window.eardanMap) window.eardanMap.show();"
assert html.count(needle)==1
html=html.replace(needle,"  if (window.eardanMap) { if (mapVisible) window.eardanMap.show(); else window.eardanMap.hide(); }")
(client/'index.html').write_text(html,encoding='utf-8')
server=(out/'server.py').read_text(encoding='utf-8')
assert "elif path in ('/map.js', '/map.css'):" in server
server=server.replace("elif path in ('/map.js', '/map.css'):","elif path in ('/map.js', '/map.css', '/eardan-atlas.html'):")
(out/'server.py').write_text(server,encoding='utf-8')
readme=(out/'README.md').read_text(encoding='utf-8')
start='- L’onglet **Carte d’Eardan** reste prévu, mais la version V14.2 faisait déjà appel aux fichiers **`map.js` et `map.css`** qui n’ont pas été fournis avec le HTML de référence. Si tu possèdes ces deux fichiers, place-les dans `client/` : ils seront chargés automatiquement. **Leur état cartographique propre n’est pas synchronisé** par cette V15 (nous n’avons pas leur code source pour le brancher correctement).'
start=next((line for line in readme.splitlines() if line.startswith("- L'onglet **Carte d'Eardan**")),None)
assert start is not None
readme=readme.replace(start,'- **Carte d’Eardan restaurée sous forme d’atlas de secours** : le paquet contient désormais `map.js`, `map.css` et `eardan-atlas.html`, une ancienne version de l’atlas interactif récupérée. Le zoom, la recherche, les vues Relief/Nations/Factions, l’hydrographie, les nouveaux repères, les fiches de lieux, les plans urbains détaillés et l’export PNG sont accessibles. Les corrections Nescya/Hakkeshu/Mushis/Fenris/Gaorens/Rohkans sont incluses. **Ce n’est pas une récupération du module Map original** : son code exact et les fonctionnalités spécifiques non incluses dans cet atlas n’étaient pas présents dans le HTML fourni. La vue de l’atlas n’est pas synchronisée entre joueurs.')
readme=readme.replace("**Le logo ou la carte manque** — Le logo et l'en-tête inclus dans le HTML sont conservés. Le module cartographique externe manque à la source, comme indiqué plus haut.",'**La carte ne s’affiche pas** — Vérifie que les trois fichiers `client/map.js`, `client/map.css` et `client/eardan-atlas.html` sont présents. La navigation « Carte d’Eardan » apparaît dès qu’une campagne est chargée. Le module cartographique original n’est pas inclus : cette V15.1 fournit un atlas de secours.')
readme=readme.replace('- `client/index.html` : la fiche V14.2 et le Craft, avec comptes, campagnes et réplication intégrés.','- `client/index.html` : la fiche V14.2 et le Craft, avec comptes, campagnes et réplication intégrés.\n- `client/map.js` + `map.css` + `eardan-atlas.html` : adaptateur et atlas interactif autonome de secours.')
readme=readme.replace('# Ethereal Realms — Client & Serveur V15','# Ethereal Realms — Client & Serveur V15.1 (restauration carte)')
(out/'README.md').write_text(readme,encoding='utf-8')
(root/'Ethereal-Realms-Client-Serveur-v15.1-Map.zip').unlink(missing_ok=True)
with zipfile.ZipFile(root/'Ethereal-Realms-Client-Serveur-v15.1-Map.zip','w',zipfile.ZIP_DEFLATED,compresslevel=8) as z:
 for p in out.rglob('*'):
  if p.is_file() and p.name not in ('__pycache__',):z.write(p,p.relative_to(root))
print('OK:',(root/'Ethereal-Realms-Client-Serveur-v15.1-Map.zip').stat().st_size, 'bytes')
for p in (client/'map.js',client/'map.css',client/'eardan-atlas.html'):
 print(p.name,p.stat().st_size)
