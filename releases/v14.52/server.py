#!/usr/bin/env python3
"""Ethereal Realms v14.52 — local/LAN multi-user, stdlib-only prototype.

Do not expose this development HTTP server directly to the public Internet.
"""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('ER_DATABASE', ROOT / 'data' / 'er.sqlite3'))
MAX_BODY = 16 * 1024 * 1024
SESSION_LIFE = 7 * 24 * 3600
USER_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]{3,32}$')
locks = threading.RLock()

class Failure(Exception):
    def __init__(self, code, message, **extras):
        super().__init__(message)
        self.code, self.extras = code, extras


def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    cx.row_factory = sqlite3.Row
    cx.execute('PRAGMA foreign_keys=ON')
    cx.execute('PRAGMA busy_timeout=10000')
    return cx


def setup():
    with database() as cx:
        cx.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
          salt TEXT NOT NULL, digest TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(tokenhash TEXT PRIMARY KEY, user TEXT NOT NULL,
          csrf TEXT NOT NULL, expiry INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY, title TEXT NOT NULL,
          owner TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS members(campaign TEXT NOT NULL, user TEXT NOT NULL,
          role TEXT NOT NULL, PRIMARY KEY(campaign,user));
        CREATE TABLE IF NOT EXISTS invites(codehash TEXT PRIMARY KEY, campaign TEXT NOT NULL,
          expiry INTEGER NOT NULL, uses INTEGER NOT NULL);
        ''')


def hash_password(password, salt):
    return hashlib.scrypt(password.encode('utf8'), salt=bytes.fromhex(salt), n=2**14,
                          r=8, p=1, maxmem=64*1024*1024).hex()


def new_id():
    return secrets.token_hex(12)


def lookup(value, path):
    cur = value
    for x in path:
        if isinstance(cur, dict) and isinstance(x, str) and x in cur:
            cur = cur[x]
        elif isinstance(cur, list) and type(x) is int and 0 <= x < len(cur):
            cur = cur[x]
        else:
            return False, None
    return True, cur


def protected_state(state):
    """Project MJ-only values regardless of how deeply an update replaces parents.

    A player cannot bypass permissions by patching `grimoire` or `characters`
    wholesale rather than targeting `pcSessionGranted` directly.
    """
    protected_names = {'pcSessionGranted', 'pcCreation', 'Points d’attribut totaux'}

    def walk(node):
        if isinstance(node, dict):
            selected = {}
            for key, value in node.items():
                child = value if key in protected_names else (walk(value) if isinstance(value, (dict, list)) else None)
                if key in protected_names or child is not None:
                    selected[key] = child
            return selected or None
        if isinstance(node, list):
            mapped = [walk(value) for value in node]
            return mapped if any(value is not None for value in mapped) else None
        return None

    extras = state.get('_extras') if isinstance(state, dict) else None
    maps = {key: value for key, value in extras.items() if 'map' in key.lower()} if isinstance(extras, dict) else {}
    return {'PC': walk(state.get('characters', [])), 'maps': maps}


def apply_diffs(state, updates, role):
    if not isinstance(updates, list) or len(updates) > 2000:
        raise Failure(400, 'Modifications invalides ou trop nombreuses.')
    if len(json.dumps(updates, ensure_ascii=False)) > MAX_BODY:
        raise Failure(413, 'Données trop volumineuses.')
    before_protected = protected_state(state) if role != 'mj' else None
    for change in updates:
        if not isinstance(change, dict):
            raise Failure(400, 'Modification invalide.')
        path = change.get('path')
        if not isinstance(path, list) or not 1 <= len(path) <= 32:
            raise Failure(400, 'Chemin de modification invalide.')
        if path[0] not in ('characters', 'pending', 'loot', 'history', '_extras'):
            raise Failure(403, 'Champ non synchronisable.')
        if any(type(x) not in (str, int) or type(x) is str and
               (len(x) > 160 or x in ('__proto__', 'constructor', 'prototype')) or
               type(x) is int and not (0 <= x < 200000) for x in path):
            raise Failure(400, 'Chemin non autorisé.')
        if role != 'mj':
            if path[0] == '_extras' and len(path) > 1 and 'map' in str(path[1]):
                raise Failure(403, 'Modification cartographique réservée au MJ.')
            if any(x in ('pcSessionGranted', 'pcCreation', 'Points d’attribut totaux') for x in path):
                raise Failure(403, 'Attribution de PC réservée au MJ.')
        if not isinstance(change.get('before'), dict) or not isinstance(change.get('after'), dict):
            raise Failure(400, 'Diff incomplet.')
        current_exists, current = lookup(state, path)
        before, after = change['before'], change['after']
        if type(before.get('exists')) is not bool or type(after.get('exists')) is not bool:
            raise Failure(400, 'État de champ invalide.')
        target_exists, target = after['exists'], after.get('value')
        if current_exists == target_exists and (not target_exists or current == target):
            continue
        if current_exists != before['exists'] or (current_exists and current != before.get('value')):
            raise Failure(409, 'Conflit : une autre personne a modifié ce champ.', path=path)
        parent_exists, parent = lookup(state, path[:-1])
        if not parent_exists:
            raise Failure(409, 'Conteneur modifié par un autre utilisateur.', path=path)
        key = path[-1]
        if isinstance(parent, dict) and isinstance(key, str):
            if target_exists:
                parent[key] = target
            else:
                parent.pop(key, None)
        elif isinstance(parent, list) and type(key) is int:
            if target_exists and key == len(parent):
                parent.append(target)
            elif 0 <= key < len(parent):
                if target_exists:
                    parent[key] = target
                else:
                    parent.pop(key)
            else:
                raise Failure(409, 'Liste modifiée par un autre utilisateur.', path=path)
        else:
            raise Failure(409, 'Conteneur incompatible.', path=path)
    if role != 'mj' and protected_state(state) != before_protected:
        raise Failure(403, 'Modification indirecte de champs MJ interdite (PC ou carte).')
    if not isinstance(state.get('characters'), list) or not state['characters']:
        raise Failure(400, 'La campagne doit contenir un personnage.')
    if len(json.dumps(state, ensure_ascii=False).encode('utf8')) > MAX_BODY:
        raise Failure(413, 'Campagne trop volumineuse.')
    return state


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'EtherealRealms/14.52'

    def log_message(self, fmt, *args):
        print('[ER]', self.address_string(), fmt % args)

    def answer(self, obj, status=200, cookie=None):
        raw = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(raw)

    def body(self):
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise Failure(415, 'Content-Type JSON requis.')
        try:
            n = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise Failure(400, 'Taille invalide.')
        if not 0 < n <= MAX_BODY:
            raise Failure(413, 'Taille de requête invalide (16 Mo maximum).')
        try:
            return json.loads(self.rfile.read(n))
        except (ValueError, UnicodeError):
            raise Failure(400, 'JSON invalide.')

    def check_origin(self):
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc.lower() != self.headers.get('Host', '').lower():
            raise Failure(403, 'Origine refusée.')

    def session(self, required=True):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            pass
        token = cookie.get('er_session')
        if not token:
            if required:
                raise Failure(401, 'Connexion nécessaire.')
            return None
        tokenhash = hashlib.sha256(token.value.encode()).hexdigest()
        with database() as cx:
            rec = cx.execute('SELECT user,csrf FROM sessions WHERE tokenhash=? AND expiry>?',
                             (tokenhash, int(time.time()))).fetchone()
        if not rec and required:
            raise Failure(401, 'Session expirée.')
        return dict(rec) if rec else None

    def write_auth(self):
        self.check_origin()
        sess = self.session()
        if not hmac.compare_digest(self.headers.get('X-ER-CSRF',''), sess['csrf']):
            raise Failure(403, 'Jeton CSRF invalide.')
        return sess

    def membership(self, cx, user, cid):
        rec = cx.execute('''SELECT campaigns.id,campaigns.title,campaigns.version,
                        campaigns.data,members.role FROM campaigns JOIN members ON
                        members.campaign=campaigns.id WHERE campaigns.id=? AND members.user=?''',
                         (cid, user)).fetchone()
        if rec is None:
            raise Failure(404, 'Campagne introuvable ou accès refusé.')
        return rec

    def list_campaigns(self, cx, user):
        return [dict(x) for x in cx.execute('''SELECT campaigns.id,campaigns.title,
          campaigns.version,members.role FROM campaigns JOIN members ON
          campaigns.id=members.campaign WHERE members.user=? ORDER BY campaigns.rowid DESC''',
          (user,)).fetchall()]

    def handle(self):
        try:
            return super().handle()
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self):
        try:
            url = urlsplit(self.path)
            path = url.path
            if path == '/api/me':
                sess = self.session(False)
                if not sess:
                    return self.answer({'authenticated': False})
                with database() as cx:
                    username = cx.execute('SELECT username FROM users WHERE id=?',(sess['user'],)).fetchone()['username']
                    camps = self.list_campaigns(cx,sess['user'])
                return self.answer({'authenticated':True,'username':username,'csrf':sess['csrf'],'campaigns':camps})
            if path == '/api/campaign':
                sess = self.session()
                cid = parse_qs(url.query).get('id',[''])[0]
                with database() as cx:
                    rec = self.membership(cx,sess['user'],cid)
                return self.answer({'id':cid,'title':rec['title'],'role':rec['role'],
                                   'version':rec['version'],'state':json.loads(rec['data'])})
            if path == '/api/version':
                sess = self.session()
                cid = parse_qs(url.query).get('id',[''])[0]
                with database() as cx:
                    rec = self.membership(cx,sess['user'],cid)
                return self.answer({'version':rec['version']})
            if path in ('/', '/index.html'):
                path = '/index.html'
            if path == '/sync.js':
                file = ROOT / 'client' / 'sync.js'
            elif path == '/index.html':
                file = ROOT / 'client' / 'index.html'
            else:
                raise Failure(404, 'Fichier introuvable.')
            raw = file.read_bytes()
            typ = 'text/javascript; charset=utf-8' if path == '/sync.js' else 'text/html; charset=utf-8'
            self.send_response(200)
            self.send_header('Content-Type',typ)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(raw)
        except Failure as e:
            self.answer({'error':str(e),**e.extras},e.code)
        except Exception as e:
            print('ER server GET error:',repr(e))
            self.answer({'error':'Erreur serveur.'},500)

    def do_POST(self):
        self.mutate('POST')

    def do_PATCH(self):
        self.mutate('PATCH')

    def mutate(self,method):
        try:
            url = urlsplit(self.path)
            path = url.path
            self.check_origin()
            if path in ('/api/register','/api/login') and method == 'POST':
                body = self.body()
                username = str(body.get('username','')).strip().lower()
                password = body.get('password')
                if not USER_PATTERN.fullmatch(username) or not isinstance(password,str):
                    raise Failure(400,'Identifiant ou mot de passe invalide.')
                if path.endswith('register') and not 10 <= len(password) <= 256:
                    raise Failure(400,'Le mot de passe doit contenir 10 à 256 caractères.')
                with locks, database() as cx:
                    cx.execute('BEGIN IMMEDIATE')
                    if path.endswith('register'):
                        if cx.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():
                            raise Failure(409,'Identifiant déjà utilisé.')
                        uid, salt = new_id(), secrets.token_hex(16)
                        cx.execute('INSERT INTO users VALUES(?,?,?,?)',
                                   (uid,username,salt,hash_password(password,salt)))
                    else:
                        record = cx.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
                        salt = record['salt'] if record else secrets.token_hex(16)
                        digest = hash_password(password,salt)
                        if record is None or not hmac.compare_digest(record['digest'],digest):
                            raise Failure(401,'Identifiants incorrects.')
                        uid=record['id']
                    token,csrf=secrets.token_urlsafe(36),secrets.token_urlsafe(22)
                    cx.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                               (hashlib.sha256(token.encode()).hexdigest(),uid,csrf,
                                int(time.time())+SESSION_LIFE))
                    cx.commit()
                secure='; Secure' if self.headers.get('X-Forwarded-Proto','')=='https' else ''
                return self.answer({'authenticated':True,'username':username,'csrf':csrf,'campaigns':[]},
                                   cookie='er_session='+token+'; HttpOnly; SameSite=Lax; Path=/; Max-Age='+str(SESSION_LIFE)+secure)
            sess=self.write_auth()
            body=self.body()
            if path == '/api/logout':
                ck=SimpleCookie();ck.load(self.headers.get('Cookie',''))
                if 'er_session' in ck:
                    with database() as cx:
                        cx.execute('DELETE FROM sessions WHERE tokenhash=?',
                                   (hashlib.sha256(ck['er_session'].value.encode()).hexdigest(),))
                return self.answer({'ok':True},cookie='er_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax')
            if path == '/api/campaigns':
                title=str(body.get('title','Nouvelle campagne')).strip()[:100] or 'Nouvelle campagne'
                state=body.get('state')
                if not isinstance(state,dict) or not isinstance(state.get('characters'),list) or not state['characters']:
                    raise Failure(400,'Fiche initiale invalide.')
                payload=json.dumps(state,ensure_ascii=False)
                if len(payload.encode())>MAX_BODY:
                    raise Failure(413,'Fiche initiale trop volumineuse.')
                cid=new_id()
                with locks,database() as cx:
                    cx.execute('BEGIN IMMEDIATE')
                    cx.execute('INSERT INTO campaigns VALUES(?,?,?,?,?)',
                               (cid,title,sess['user'],1,payload))
                    cx.execute('INSERT INTO members VALUES(?,?,?)',(cid,sess['user'],'mj'))
                    cx.commit()
                return self.answer({'id':cid,'version':1,'role':'mj'})
            if path == '/api/invite':
                cid=str(body.get('id',''))
                with locks,database() as cx:
                    member=self.membership(cx,sess['user'],cid)
                    if member['role']!='mj':
                        raise Failure(403,'Seul le MJ peut inviter.')
                    token=secrets.token_urlsafe(18)
                    cx.execute('INSERT INTO invites VALUES(?,?,?,?)',
                               (hashlib.sha256(token.encode()).hexdigest(),cid,int(time.time())+86400,10))
                return self.answer({'code':token,'expiresInHours':24})
            if path == '/api/join':
                token=str(body.get('code','')).strip()
                with locks,database() as cx:
                    cx.execute('BEGIN IMMEDIATE')
                    rec=cx.execute('SELECT * FROM invites WHERE codehash=? AND expiry>? AND uses>0',
                                   (hashlib.sha256(token.encode()).hexdigest(),int(time.time()))).fetchone()
                    if rec is None:
                        raise Failure(404,'Invitation invalide ou expirée.')
                    cx.execute('INSERT OR IGNORE INTO members VALUES(?,?,?)',(rec['campaign'],sess['user'],'joueur'))
                    cx.execute('UPDATE invites SET uses=uses-1 WHERE codehash=?',(rec['codehash'],))
                    cx.commit()
                return self.answer({'id':rec['campaign'],'role':'joueur'})
            if path == '/api/campaign' and method == 'PATCH':
                cid=str(body.get('id',''))
                changes=body.get('changes')
                with locks,database() as cx:
                    cx.execute('BEGIN IMMEDIATE')
                    rec=self.membership(cx,sess['user'],cid)
                    state=json.loads(rec['data'])
                    state=apply_diffs(state,changes,rec['role'])
                    payload=json.dumps(state,ensure_ascii=False,separators=(',',':'))
                    cx.execute('UPDATE campaigns SET data=?,version=version+1 WHERE id=?',(payload,cid))
                    cx.commit()
                return self.answer({'version':rec['version']+1,'state':state})
            raise Failure(404,'Action introuvable.')
        except Failure as e:
            return self.answer({'error':str(e),**e.extras},e.code)
        except Exception as e:
            print('ER server write error:',repr(e))
            return self.answer({'error':'Erreur serveur.'},500)


def main():
    parser=argparse.ArgumentParser(description='Serveur local Ethereal Realms')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    setup()
    with Server((args.host,args.port),Handler) as httpd:
        print(f'Ethereal Realms v14.52 -> http://{args.host}:{args.port}',flush=True)
        try:
            httpd.serve_forever(poll_interval=.25)
        except KeyboardInterrupt:
            pass

if __name__=='__main__':
    main()