/* Ethereal Realms v14.52 — bridge API; no third-party libraries. */
(() => {
  'use strict';
  const DATA_KEY = 'ethereal-realms:fiche-locale:v1';
  const EXTRA_KEYS = ['ethereal-realms-eardan-map-v1', 'ethereal-realms-eardan-layers-v1', 'ethereal-realms:illustrations:v1'];
  const rawSet = Storage.prototype.setItem;
  let csrf = '', account = '', currentId = '', role = 'joueur', serverSnapshot = null;
  let sending = false, dirty = false, suspended = false, notifyTimer = 0, pollBusy = false;
  let localInitial = localStorage.getItem(DATA_KEY);
  let localExtrasInitial = Object.fromEntries(EXTRA_KEYS.map(k => [k, localStorage.getItem(k)]));
  const el = (tag, attrs = {}, parent) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'text') e.textContent = v;
      else if (k === 'className') e.className = v;
      else e.setAttribute(k, v);
    }
    if (parent) parent.appendChild(e);
    return e;
  };
  const style = el('style', {text: `
  .er-online-overlay{position:fixed;inset:0;z-index:20000;background:rgba(24,17,35,.83);display:flex;align-items:center;justify-content:center;padding:20px;font:14px system-ui,sans-serif}
  .er-online-card{width:min(520px,100%);max-height:90vh;overflow:auto;padding:25px;border-radius:12px;background:#fffaf1;color:#392a43;box-shadow:0 25px 90px #100a17aa}
  .er-online-overlay[hidden]{display:none!important}
  .er-online-card h2{font:28px Georgia,serif;margin:0 0 10px;color:#573b6e}
  .er-online-card p{line-height:1.5}
  .er-online-card label{display:block;margin:10px 0;font-weight:600;font-size:13px}
  .er-online-card input{box-sizing:border-box;width:100%;padding:10px;border:1px solid #ccb9d2;border-radius:7px;margin-top:5px;font:inherit}
  .er-online-card button{cursor:pointer;padding:9px 14px;margin:5px 6px 5px 0;border:1px solid #ad90be;border-radius:7px;background:#f1e7f6;color:#432754;font:600 13px system-ui,sans-serif}
  .er-online-card button.main{background:#65447c;color:#fff}
  .er-online-card button:disabled{opacity:.5;cursor:wait}
  .er-online-error{color:#a53245;white-space:pre-wrap;min-height:1.5em}
  .er-online-status{position:fixed;right:15px;bottom:15px;z-index:19000;background:#32253f;color:white;padding:7px 12px;border-radius:7px;font:12px system-ui;box-shadow:0 2px 10px #0005}
  .er-online-status button{margin-left:10px;border:0;background:#ebdcee;color:#36233d;border-radius:4px;cursor:pointer;padding:4px 7px}
  .er-online-campaign{padding:8px;border-bottom:1px solid #eadfee}
  .er-online-campaign strong{display:inline-block;min-width:180px}
  `}, document.head);
  const overlay = el('div', {className:'er-online-overlay',role:'dialog','aria-modal':'true'}, document.body);
  const card = el('div',{className:'er-online-card'},overlay);
  const status = el('div',{className:'er-online-status',text:'Connexion au serveur…'},document.body);
  status.hidden = true;
  let lastError = null;
  function message(msg){
    lastError = msg;
    const p = card.querySelector('.er-online-error');
    if(p)p.textContent=msg || '';
  }
  function resetCard(title, desc=''){
    card.replaceChildren();
    el('h2',{text:title},card);
    if(desc)el('p',{text:desc},card);
    el('div',{className:'er-online-error'},card);
  }
  function field(label,type='text',value=''){
    const wrap = el('label',{text:label},card);
    const input=el('input',{type,value},wrap);
    return input;
  }
  function action(text, fn, primary=false){
    const b=el('button',{type:'button',text,className:primary?'main':''},card);
    b.addEventListener('click', async ()=>{
      b.disabled=true;
      try {message(''); await fn();} catch(e) {message(e.message);}
      finally {b.disabled=false;}
    });
    return b;
  }
  async function api(path,method='GET',obj){
    const res=await fetch(path,{method,headers:{...(obj?{'Content-Type':'application/json'}:{}), ...(csrf?{'X-ER-CSRF':csrf}:{})},body:obj?JSON.stringify(obj):undefined,credentials:'same-origin',cache:'no-store'});
    let data;
    try {data=await res.json();}catch {throw Error('Réponse serveur illisible.');}
    if(!res.ok)throw Object.assign(Error(data.error||`Serveur ${res.status}`),{code:res.status,path:data.path});
    return data;
  }
  function showLogin(mode='login'){
    overlay.hidden=false;
    resetCard('Ethereal Realms — Connexion','Le serveur héberge les comptes, les campagnes et la sauvegarde synchronisée.');
    const username=field('Identifiant (3–32 caractères)');
    const password=field('Mot de passe (10 caractères minimum)','password');
    action(mode==='register'?'Créer mon compte':'Me connecter',async()=>{
      const info=await api('/api/'+mode,'POST',{username:username.value,password:password.value});
      csrf=info.csrf;account=info.username;
      await showCampaigns();
    },true);
    action(mode==='register'?'J’ai déjà un compte':'Créer un compte',()=>showLogin(mode==='register'?'login':'register'));
    el('p',{text:'Pour tester entre deux appareils, utilise la même adresse du serveur. Ne publie pas ce serveur de développement directement sur Internet.'},card);
  }
  async function showCampaigns(){
    const data=await api('/api/me');
    if(!data.authenticated){csrf='';return showLogin();}
    csrf=data.csrf;account=data.username;
    overlay.hidden=false;
    resetCard('Campagnes — '+account,'Choisis une campagne existante, importe ta fiche locale ou crée une nouvelle campagne.');
    for(const c of data.campaigns){
      const box=el('div',{className:'er-online-campaign'},card);
      el('strong',{text:c.title},box);
      const b=el('button',{text:'Ouvrir · '+(c.role==='mj'?'MJ':'Joueur'),type:'button'},box);
      b.addEventListener('click',async()=>{try{await enter(c.id);}catch(e){message(e.message);}});
    }
    const title=field('Nom de la nouvelle campagne','text','Ma campagne Ethereal Realms');
    action('Créer une campagne vierge',async()=>{
      const blank=blankCampaign();
      await createCampaign(title.value,blank);
    },true);
    if(localInitial){
      action('Importer ma fiche v14.51 locale',async()=>{
        let data;
        try{data=JSON.parse(localInitial);}catch{throw Error('Sauvegarde locale illisible.');}
        if(!data?.characters?.length)throw Error('Sauvegarde locale incompatible.');
        data._extras = Object.fromEntries(Object.entries(localExtrasInitial).filter(([,v])=>v!==null));
        await createCampaign(title.value,data);
      });
    }
    const invite=field('Code d’invitation reçu d’un MJ');
    action('Rejoindre une campagne',async()=>{
      const joined=await api('/api/join','POST',{code:invite.value.trim()});
      await enter(joined.id);
    });
    action('Se déconnecter',async()=>{await api('/api/logout','POST',{});csrf='';showLogin();});
  }
  async function createCampaign(title,state){
    const result=await api('/api/campaigns','POST',{title,state});
    await enter(result.id);
  }
  function snapshot(){
    const state=structuredClone(campaign);
    state._extras = Object.fromEntries(EXTRA_KEYS.map(k=>[k,localStorage.getItem(k)]).filter(([,v])=>v!==null));
    return state;
  }
  function writeLocal(data){
    suspended=true;
    try{
      rawSet.call(localStorage,DATA_KEY,JSON.stringify(data));
      for(const k of EXTRA_KEYS){
        if(data._extras && Object.hasOwn(data._extras,k))rawSet.call(localStorage,k,data._extras[k]);
      }
      campaign=structuredClone(data);
      refreshView();
      // Apply map changes to the live map without requiring page reload.
      if(window.eardanMap?.applyServerState && data._extras?.['ethereal-realms-eardan-map-v1']){
        try{window.eardanMap.applyServerState(JSON.parse(data._extras['ethereal-realms-eardan-map-v1']));}catch{}
      }
    }finally{suspended=false;}
  }
  function note(){
    status.replaceChildren();
    el('span',{text:`${account} · ${role==='mj'?'MJ':'Joueur'} · ${currentId?'Connecté':'Déconnecté'}${dirty?' · Modifications en cours…':''}`},status);
    const manage=el('button',{text:'Campagnes'},status);
    manage.addEventListener('click',()=>showManage().catch(e=>message(e.message)));
  }
  async function enter(cid){
    const result=await api('/api/campaign?id='+encodeURIComponent(cid));
    currentId=cid;role=result.role;serverSnapshot=structuredClone(result.state);
    dirty=false;clearTimeout(notifyTimer);
    writeLocal(result.state);
    if(window.eardanMap?.setServerRole)window.eardanMap.setServerRole(role);
    // Disable the local spoofable PC privilege toggle for non-MJ accounts.
    document.documentElement.dataset.erOnlineRole=role;
    overlay.hidden=true;status.hidden=false;note();
  }
  async function showManage(){
    overlay.hidden=false;
    resetCard('Gestion de campagne','Campagne active : '+currentId+' · rôle '+role);
    if(role==='mj'){
      action('Créer un code d’invitation',async()=>{
        const res=await api('/api/invite','POST',{id:currentId});
        el('p',{text:'Code à transmettre (valable 24 h, 10 utilisations) : '+res.code},card);
      });
    }
    action('Revenir à la fiche',()=>{overlay.hidden=true;});
    action('Changer de campagne',showCampaigns);
    action('Se déconnecter',async()=>{await api('/api/logout','POST',{});csrf='';currentId='';status.hidden=true;showLogin();});
  }
  function diff(a,b,path=[],out=[]){
    if(Object.is(a,b))return out;
    if(a===null||b===null||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b)){
      out.push({path,before:{exists:a!==undefined,value:a},after:{exists:b!==undefined,value:b}});return out;
    }
    if(Array.isArray(a) && a.length!==b.length){
      out.push({path,before:{exists:true,value:a},after:{exists:true,value:b}});return out;
    }
    const keys = Array.isArray(a)?Array.from({length:a.length},(_,i)=>i):[...new Set([...Object.keys(a),...Object.keys(b)])];
    for(const key of keys){
      const pa=Array.isArray(a)?a[key]:Object.hasOwn(a,key)?a[key]:undefined;
      const pb=Array.isArray(b)?b[key]:Object.hasOwn(b,key)?b[key]:undefined;
      diff(pa,pb,[...path,key],out);
    }
    return out;
  }
  function setPath(target,path,after){
    let parent=target;
    for(const k of path.slice(0,-1)) parent=parent[k];
    const k=path.at(-1);
    if(after.exists)parent[k]=structuredClone(after.value);
    else if(Array.isArray(parent))parent.splice(k,1);
    else delete parent[k];
  }
  async function flush(){
    if(!currentId||!dirty||sending)return;
    sending=true;dirty=false;note();
    const before=structuredClone(serverSnapshot);
    const sentState=snapshot();
    const changes=diff(before,sentState);
    if(!changes.length){sending=false;note();return;}
    try{
      const reply=await api('/api/campaign','PATCH',{id:currentId,changes});
      const afterLocal=snapshot();
      const pending=diff(sentState,afterLocal);
      serverSnapshot=structuredClone(reply.state);
      if(pending.length){
        const next=structuredClone(reply.state);
        try{for(const change of pending)setPath(next,change.path,change.after);}catch{
          // Preserve existing draft for manual conflict resolution.
          rawSet.call(localStorage,DATA_KEY,JSON.stringify(afterLocal));
          throw Error('Nouvelle modification non réconciliée. Exporte ta copie locale.');
        }
        writeLocal(next);dirty=true;
      }else writeLocal(reply.state);
    }catch(err){
      dirty=true;
      if(err.code===409||err.code===403){
        overlay.hidden=false;
        resetCard(err.code===403?'Action refusée':'Conflit de synchronisation',err.message+' Aucune donnée distante n’a été écrasée.');
        action('Exporter la copie locale JSON',()=>{
          const blob=new Blob([JSON.stringify(snapshot(),null,2)],{type:'application/json'});
          const url=URL.createObjectURL(blob);
          const link=document.createElement('a');link.href=url;link.download='ER-sauvegarde-conflit.json';link.click();
          setTimeout(()=>URL.revokeObjectURL(url),1500);
        });
        action('Recharger la version serveur',async()=>{
          const remote=await api('/api/campaign?id='+encodeURIComponent(currentId));
          serverSnapshot=structuredClone(remote.state);dirty=false;writeLocal(remote.state);overlay.hidden=true;note();
        });
      }else{status.firstChild && (status.firstChild.textContent='Hors ligne — modifications locales conservées');}
    }finally{sending=false;note();if(dirty && overlay.hidden)notifyTimer=setTimeout(flush,1800);}
  }
  function changed(){
    if(suspended||!currentId)return;
    dirty=true;note();clearTimeout(notifyTimer);notifyTimer=setTimeout(flush,380);
  }
  Storage.prototype.setItem=function(key,value){
    const result=rawSet.call(this,key,value);
    if(this===localStorage && (key===DATA_KEY||EXTRA_KEYS.includes(key)))changed();
    return result;
  };
  async function poll(){
    if(!currentId||sending||dirty||pollBusy||!overlay.hidden)return;
    pollBusy=true;
    try{
      const version=await api('/api/version?id='+encodeURIComponent(currentId));
      if(version.version!==undefined){
        // Even if the last push was ours, don't stomp unsaved edits.
        const current=await api('/api/campaign?id='+encodeURIComponent(currentId));
        if(!dirty && JSON.stringify(current.state)!==JSON.stringify(serverSnapshot)){
          serverSnapshot=structuredClone(current.state);
          writeLocal(current.state);
        }
      }
    }catch(e){status.firstChild && (status.firstChild.textContent='Connexion perdue — reprise automatique');}
    finally{pollBusy=false;}
  }
  // Keep UI role switch from granting PC session awards to non-MJ clients.
  document.addEventListener('click',evt=>{
    if(role==='mj'||!currentId)return;
    const b=evt.target.closest('button');
    if(b && /Activer MJ/i.test(b.textContent||'')){
      evt.preventDefault();evt.stopImmediatePropagation();
      alert('Seul le Maître du jeu peut attribuer des PC de session sur le serveur.');
    }
  },true);
  (async()=>{
    try{const me=await api('/api/me');if(me.authenticated){csrf=me.csrf;account=me.username;await showCampaigns();}else showLogin();}
    catch(e){resetCard('Serveur indisponible',e.message+' Vérifie que tu ouvres l’adresse du serveur Python et non le fichier HTML directement.');}
  })();
  setInterval(poll,2300);
  window.EROnline={status:()=>({currentId,role,dirty,account}),flush};
})();