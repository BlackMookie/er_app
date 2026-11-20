#!/usr/bin/env python3
"""Reconstitue l'archive v14.52 depuis les fichiers archive-parts/*.b64."""
import base64
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARTS = ROOT / 'archive-parts'
EXPECTED_SHA256 = '3936c34f69a84325f462f59af15e6d37e3756bdefd2030ccb0235018f488e407'

parts = sorted(PARTS.glob('archive-*.b64'))
if len(parts) != 18:
    raise SystemExit(f'Archive incomplète : {len(parts)} fragments présents sur 18 attendus.')
text = ''.join(path.read_text(encoding='ascii').strip() for path in parts)
raw = base64.b64decode(text, validate=True)
sha = hashlib.sha256(raw).hexdigest()
if sha != EXPECTED_SHA256:
    raise SystemExit(f'Erreur d’intégrité SHA-256 : {sha} != {EXPECTED_SHA256}')
out = ROOT / 'Ethereal-Realms-v14.52-Client-Serveur.zip'
out.write_bytes(raw)
print(f'Archive reconstituée et vérifiée : {out.name} ({len(raw)} octets)')