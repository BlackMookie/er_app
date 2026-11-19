#!/usr/bin/env python3
"""Ethereal Realms V15 — serveur HTTP/SQLite/SSE, dépendances Python stdlib uniquement."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import signal
import sqlite3
import sys
import time
import traceback
from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
WEBROOT = ROOT / 'client'
DB_PATH = Path(os.environ.get('ER_DB_PATH', ROOT / 'data' / 'ethereal_realms.sqlite3'))
MAX_BODY = 5 * 1024 * 1024
SESSION_SECONDS = 7 * 24 * 3600
MISSING = object()
IDENT = re.compile(r'^[a-zA-Z0-9_.-]{3,32}$')


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def new_id():
    return secrets.token_hex(16)


def db():
    cx = sqlite3.connect(str(DB_PATH), timeout=10, isolation_level=None)
    cx.row_factory = sqlite3.Row
    cx.execute('PRAGMA foreign_keys=ON')
    cx.execute('PRAGMA busy_timeout=10000')
    return cx


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as cx:
        cx.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(
                id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
                password_salt TEXT NOT NULL, password_digest TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                csrf TEXT NOT NULL, expires_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS campaigns(
                id TEXT PRIMARY KEY, title TEXT NOT NULL, owner_id TEXT NOT NULL REFERENCES users(id),
                version INTEGER NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS members(
                campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL, PRIMARY KEY(campaign_id,user_id));
            CREATE TABLE IF NOT EXISTS invitations(
                code_hash TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL, uses_left INTEGER NOT NULL);
        ''')


def pass_digest(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=2**14, r=8, p=1,
                          maxmem=64 * 1024 * 1024).hex()


def blank_campaign():
    return {
        'characters': [{
            'id': 'local', 'name': '', 'detail': '', 'portrait': None,
            'base': dict.fromkeys(['FOR', 'DEX', 'INT', 'SAG', 'CHA', 'VOL', 'PER', 'CON'], 0),
            'racial': {}, 'armor': {}, 'equipped': None, 'weapons': [], 'inventory': [],
            'skills': [
                ['Furtivité', 'DEX', 'PER', 0], ['Négociation', 'CHA', 'INT', 0],
                ['Maîtrise des Armes Courtes', 'DEX', 'FOR', 0], ['Parade', 'DEX', 'FOR', 0],
                ['Esquive', 'DEX', 'FOR', 0], ['Observation', 'PER', 'INT', 0],
                ['Orientation', 'PER', 'INT', 0], ['Choix d’itinéraire', 'PER', 'SAG', 0],
            ]
        }], 'pending': [], 'loot': [], 'history': []
    }


def validate_campaign(data):
    if not isinstance(data, dict) or not isinstance(data.get('characters'), list) or not data['characters']:
        raise APIError(400, 'Fiche invalide : personnages manquants.')
    if len(data['characters']) > 10 or not isinstance(data['characters'][0], dict):
        raise APIError(400, 'Fiche invalide : structure des personnages.')
    if not isinstance(data['characters'][0].get('base'), dict) or not isinstance(data['characters'][0].get('skills'), list):
        raise APIError(400, 'Fiche invalide : attributs ou compétences.')
    if len(json.dumps(data, ensure_ascii=False).encode('utf-8')) > MAX_BODY:
        raise APIError(413, 'La fiche dépasse 5 Mo.')


class APIError(Exception):
    def __init__(self, status, message, **extra):
        super().__init__(message)
        self.status = int(status)
        self.extra = extra


def loc(root, path):
    cur = root
    for key in path:
        if isinstance(cur, dict) and isinstance(key, str) and key in cur:
            cur = cur[key]
        elif isinstance(cur, list) and type(key) is int and 0 <= key < len(cur):
            cur = cur[key]
        else:
            return MISSING
    return cur


def assign(root, path, present, value):
    if not path:
        raise APIError(400, 'Chemin de modification vide.')
    parent = loc(root, path[:-1])
    if parent is MISSING:
        raise APIError(409, 'Conflit : le conteneur du champ a changé.')
    key = path[-1]
    if isinstance(parent, dict) and isinstance(key, str):
        if present:
            parent[key] = deepcopy(value)
        else:
            parent.pop(key, None)
    elif isinstance(parent, list) and type(key) is int and 0 <= key < len(parent):
        if present:
            parent[key] = deepcopy(value)
        else:
            parent.pop(key)
    else:
        raise APIError(409, 'Conflit : la liste ou le champ a changé.')


def safe_path(path):
    if not isinstance(path, list) or not 1 <= len(path) <= 30:
        return False
    if path[0] not in ('characters', 'pending', 'loot', 'history'):
        return False
    return all((isinstance(p, str) and len(p) <= 160 and p not in ('__proto__', 'prototype', 'constructor'))
               or (type(p) is int and 0 <= p < 50000) for p in path)


def apply_changes(state, changes):
    if not isinstance(changes, list) or len(changes) > 1200:
        raise APIError(400, 'Liste de modifications invalide ou trop longue.')
    changed = False
    for item in changes:
        if not isinstance(item, dict) or not safe_path(item.get('path')):
            raise APIError(400, 'Chemin de modification interdit.')
        old, new = item.get('old'), item.get('new')
        if not isinstance(old, dict) or not isinstance(new, dict) or type(old.get('present')) is not bool or type(new.get('present')) is not bool:
            raise APIError(400, 'Valeurs de comparaison invalides.')
        if old['present'] and 'value' not in old or new['present'] and 'value' not in new:
            raise APIError(400, 'Valeur de modification manquante.')
        path = item['path']
        current = loc(state, path)
        expected = old.get('value', MISSING) if old['present'] else MISSING
        target = new.get('value', MISSING) if new['present'] else MISSING
        if (current is MISSING and target is MISSING) or (current is not MISSING and target is not MISSING and current == target):
            continue  # Idempotence sur une modification rejouée.
        if not ((current is MISSING and expected is MISSING) or
                (current is not MISSING and expected is not MISSING and current == expected)):
            raise APIError(409, 'Conflit : ce champ a été modifié sur un autre appareil.',
                           conflict_path=path)
        assign(state, path, new['present'], new.get('value'))
        changed = True
    return changed


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'EtherealRealms/15'

    def log_message(self, fmt, *args):
        sys.stderr.write('[%s] %s %s\n' % (self.log_date_time_string(), self.address_string(), fmt % args))

    def common_headers(self, size=0, ctype='application/json; charset=utf-8', code=200, cookie=None, streaming=False):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-store')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        if streaming:
            self.send_header('Connection', 'keep-alive')
        else:
            self.send_header('Content-Length', str(size))
        self.end_headers()

    def send_json(self, data, code=200, cookie=None):
        b = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.common_headers(len(b), code=code, cookie=cookie)
        self.wfile.write(b)

    def read_json(self):
        typ = self.headers.get('Content-Type', '').split(';')[0].strip()
        if typ != 'application/json':
            raise APIError(415, 'Content-Type application/json requis.')
        try:
            n = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise APIError(400, 'Taille de requête invalide.')
        if not 0 < n <= MAX_BODY:
            raise APIError(413, 'Requête vide ou trop volumineuse (maximum 5 Mo).')
        try:
            return json.loads(self.rfile.read(n))
        except (UnicodeError, json.JSONDecodeError):
            raise APIError(400, 'JSON invalide.')

    def validate_origin(self):
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc.lower() != self.headers.get('Host', '').lower():
            raise APIError(403, 'Origine de requête refusée.')

    def session(self, required=True):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            pass
        morsel = cookie.get('er_session')
        tok = morsel.value if morsel else None
        if not tok:
            if required:
                raise APIError(401, 'Connexion nécessaire.')
            return None
        h = hashlib.sha256(tok.encode()).hexdigest()
        with db() as cx:
            row = cx.execute('''SELECT s.user_id,s.csrf,u.username,u.display_name
                                FROM sessions s JOIN users u ON u.id=s.user_id
                                WHERE s.token_hash=? AND s.expires_at>?''', (h, int(time.time()))).fetchone()
        if not row and required:
            raise APIError(401, 'Session expirée. Reconnecte-toi.')
        return dict(row) if row else None

    def csrf(self, session):
        if not hmac.compare_digest(self.headers.get('X-ER-CSRF', ''), session['csrf']):
            raise APIError(403, 'Jeton CSRF invalide.')

    def make_cookie(self, token, clear=False):
        attrs = '; Path=/; HttpOnly; SameSite=Lax'
        if self.headers.get('X-Forwarded-Proto', '').split(',')[0].strip() == 'https':
            attrs += '; Secure'
        if clear:
            return 'er_session=; Max-Age=0' + attrs
        return 'er_session=' + token + '; Max-Age=' + str(SESSION_SECONDS) + attrs

    def create_session(self, cx, user_id):
        token = secrets.token_urlsafe(42)
        csrf = secrets.token_urlsafe(28)
        cx.execute('INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES(?,?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(), user_id, csrf, int(time.time()) + SESSION_SECONDS))
        return token, csrf

    def list_campaigns(self, cx, uid):
        return [dict(row) for row in cx.execute('''SELECT c.id,c.title,c.version,c.updated_at,m.role
                      FROM members m JOIN campaigns c ON c.id=m.campaign_id
                      WHERE m.user_id=? ORDER BY c.updated_at DESC''', (uid,)).fetchall()]

    def membership(self, cx, uid, campaign_id):
        row = cx.execute('''SELECT c.id,c.title,c.version,c.state,c.owner_id,m.role
                         FROM campaigns c JOIN members m ON c.id=m.campaign_id
                         WHERE c.id=? AND m.user_id=?''', (campaign_id, uid)).fetchone()
        if not row:
            raise APIError(404, 'Campagne introuvable ou accès refusé.')
        return row

    def auth(self, route, body):
        name = str(body.get('username', '')).strip()
        password = body.get('password', '')
        if not IDENT.fullmatch(name) or not isinstance(password, str):
            raise APIError(400, 'Identifiant invalide (3 à 32 caractères : lettres, chiffres, _, -, .).')
        if route == 'register' and not 10 <= len(password) <= 256:
            raise APIError(400, 'Mot de passe de 10 à 256 caractères requis.')
        username = name.casefold()
        with db() as cx:
            cx.execute('BEGIN IMMEDIATE')
            if route == 'register':
                if cx.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
                    raise APIError(409, 'Cet identifiant existe déjà.')
                uid, salt, cid = new_id(), secrets.token_hex(16), new_id()
                digest = pass_digest(password, salt)
                cx.execute('INSERT INTO users VALUES(?,?,?,?,?,?)', (uid, username, name, salt, digest, utcnow()))
                cx.execute('INSERT INTO campaigns VALUES(?,?,?,?,?,?)',
                           (cid, 'Campagne de ' + name, uid, 1, json.dumps(blank_campaign(), ensure_ascii=False), utcnow()))
                cx.execute('INSERT INTO members VALUES(?,?,?)', (cid, uid, 'owner'))
            else:
                row = cx.execute('SELECT id,password_salt,password_digest FROM users WHERE username=?', (username,)).fetchone()
                if not row:
                    raise APIError(401, 'Identifiant ou mot de passe incorrect.')
                uid = row['id']
                if not hmac.compare_digest(pass_digest(password, row['password_salt']), row['password_digest']):
                    raise APIError(401, 'Identifiant ou mot de passe incorrect.')
            token, csrf = self.create_session(cx, uid)
            campaigns = self.list_campaigns(cx, uid)
            cx.commit()
        self.send_json({'user': {'username': name}, 'csrf': csrf, 'campaigns': campaigns}, cookie=self.make_cookie(token))

    def get_route(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == '/api/health':
            return self.send_json({'status': 'ok', 'version': 15, 'storage': 'sqlite'})
        if path == '/api/me':
            sess = self.session()
            with db() as cx:
                campaigns = self.list_campaigns(cx, sess['user_id'])
            return self.send_json({'user': {'username': sess['display_name']}, 'csrf': sess['csrf'], 'campaigns': campaigns})
        found = re.fullmatch(r'/api/campaigns/([0-9a-f]{32})(?:/(events))?', path)
        if found:
            sess = self.session()
            cid, suffix = found.group(1), found.group(2)
            if suffix == 'events':
                return self.events(cid, sess)
            with db() as cx:
                row = self.membership(cx, sess['user_id'], cid)
            return self.send_json({'id': cid, 'title': row['title'], 'version': row['version'], 'state': json.loads(row['state'])})
        if path.startswith('/api/'):
            raise APIError(404, 'API inconnue.')
        self.static(path)

    def events(self, cid, sess):
        with db() as cx:
            self.membership(cx, sess['user_id'], cid)
        self.common_headers(ctype='text/event-stream; charset=utf-8', streaming=True)
        latest = -1
        count = 0
        try:
            while True:
                with db() as cx:
                    row = cx.execute('SELECT version FROM campaigns WHERE id=?', (cid,)).fetchone()
                if not row:
                    break
                version = row['version']
                if version != latest:
                    msg = f'event: change\ndata: {json.dumps({"version": version})}\n\n'.encode()
                    self.wfile.write(msg)
                    self.wfile.flush()
                    latest = version
                elif count % 12 == 0:
                    self.wfile.write(b': heartbeat\n\n')
                    self.wfile.flush()
                count += 1
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return

    def static(self, path):
        if path in ('/', '/index.html'):
            file = WEBROOT / 'index.html'
        elif path in ('/map.js', '/map.css', '/eardan-atlas.html'):
            file = WEBROOT / path.lstrip('/')
        else:
            raise APIError(404, 'Fichier introuvable.')
        if not file.is_file():
            raise APIError(404, 'Module cartographique facultatif non fourni.')
        data = file.read_bytes()
        mime = mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
        self.common_headers(len(data), mime + ('; charset=utf-8' if mime.startswith('text/') else ''))
        self.wfile.write(data)

    def post_route(self):
        self.validate_origin()
        path = urlsplit(self.path).path
        if path in ('/api/auth/register', '/api/auth/login'):
            return self.auth(path.rsplit('/', 1)[-1], self.read_json())
        sess = self.session()
        self.csrf(sess)
        if path == '/api/auth/logout':
            self.read_json()
            cookie = SimpleCookie()
            cookie.load(self.headers.get('Cookie', ''))
            val = cookie.get('er_session')
            if val:
                with db() as cx:
                    cx.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(val.value.encode()).hexdigest(),))
            return self.send_json({'ok': True}, cookie=self.make_cookie('', True))
        if path == '/api/campaigns':
            body = self.read_json()
            title = str(body.get('title', '')).strip()
            if not 1 <= len(title) <= 100:
                raise APIError(400, 'Nom de campagne de 1 à 100 caractères requis.')
            state = body.get('state') or blank_campaign()
            validate_campaign(state)
            cid = new_id()
            with db() as cx:
                cx.execute('BEGIN IMMEDIATE')
                cx.execute('INSERT INTO campaigns VALUES(?,?,?,?,?,?)', (cid, title, sess['user_id'], 1, json.dumps(state, ensure_ascii=False), utcnow()))
                cx.execute('INSERT INTO members VALUES(?,?,?)', (cid, sess['user_id'], 'owner'))
                cx.commit()
            return self.send_json({'id': cid, 'version': 1})
        if path == '/api/invites/join':
            code = str(self.read_json().get('code', '')).strip()
            if not code or len(code) > 150:
                raise APIError(400, 'Code invalide.')
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            with db() as cx:
                cx.execute('BEGIN IMMEDIATE')
                inv = cx.execute('SELECT * FROM invitations WHERE code_hash=?', (code_hash,)).fetchone()
                if not inv or inv['expires_at'] <= time.time() or inv['uses_left'] <= 0:
                    raise APIError(404, 'Invitation inconnue ou expirée.')
                exists = cx.execute('SELECT 1 FROM members WHERE campaign_id=? AND user_id=?',
                                    (inv['campaign_id'], sess['user_id'])).fetchone()
                if not exists:
                    cx.execute('INSERT INTO members VALUES(?,?,?)', (inv['campaign_id'], sess['user_id'], 'editor'))
                    cx.execute('UPDATE invitations SET uses_left=uses_left-1 WHERE code_hash=?', (code_hash,))
                cx.commit()
            return self.send_json({'id': inv['campaign_id'], 'joined': not bool(exists)})
        found = re.fullmatch(r'/api/campaigns/([0-9a-f]{32})/(patch|invites)', path)
        if found:
            cid, route = found.groups()
            if route == 'invites':
                self.read_json()
                with db() as cx:
                    member = self.membership(cx, sess['user_id'], cid)
                    if member['role'] != 'owner':
                        raise APIError(403, 'Seul le propriétaire peut inviter.')
                    code = secrets.token_urlsafe(16)
                    cx.execute('INSERT INTO invitations VALUES(?,?,?,?)',
                               (hashlib.sha256(code.encode()).hexdigest(), cid, int(time.time()) + 24 * 3600, 10))
                return self.send_json({'code': code, 'expires_in_hours': 24, 'uses': 10})
            body = self.read_json()
            with db() as cx:
                cx.execute('BEGIN IMMEDIATE')
                row = self.membership(cx, sess['user_id'], cid)
                data = json.loads(row['state'])
                did_change = apply_changes(data, body.get('changes'))
                validate_campaign(data)
                if did_change:
                    ver = row['version'] + 1
                    cx.execute('UPDATE campaigns SET state=?,version=?,updated_at=? WHERE id=?',
                               (json.dumps(data, ensure_ascii=False, separators=(',', ':')), ver, utcnow(), cid))
                else:
                    ver = row['version']
                cx.commit()
            return self.send_json({'id': cid, 'version': ver, 'state': data})
        raise APIError(404, 'Action inconnue.')

    def do_GET(self):
        try:
            self.get_route()
        except APIError as e:
            self.send_json({'error': str(e), **e.extra}, e.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc()
            self.send_json({'error': 'Erreur interne du serveur.'}, 500)

    def do_POST(self):
        try:
            self.post_route()
        except APIError as e:
            self.send_json({'error': str(e), **e.extra}, e.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc()
            self.send_json({'error': 'Erreur interne du serveur.'}, 500)


def main():
    parser = argparse.ArgumentParser(description='Ethereal Realms — serveur V15 (Python 3.10+)')
    parser.add_argument('--host', default='127.0.0.1', help='127.0.0.1 ou 0.0.0.0 pour le réseau local')
    parser.add_argument('--port', default=8765, type=int)
    args = parser.parse_args()
    init_db()
    server = Server((args.host, args.port), Handler)
    print(f'ER V15 disponible sur http://{args.host}:{args.port} (Ctrl+C pour fermer)', flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()