/* Adaptateur Carte d’Eardan : atlas embarqué, sans dépendance externe. */
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
