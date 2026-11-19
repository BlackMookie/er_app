#!/usr/bin/env python3
"""Restaure les assets binaires archivés en morceaux dans GitHub."""
from pathlib import Path
import base64
import hashlib

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PARTS = sorted(ASSETS.glob("Hunters_Academy.png.b64.part*"))
if len(PARTS) != 3:
    raise SystemExit("Trois fragments sont requis pour reconstruire Hunters Academy.png.")
encoded = "".join("".join(path.read_text(encoding="ascii").split()) for path in PARTS)
data = base64.b64decode(encoded, validate=True)
checksum = hashlib.sha256(data).hexdigest()
expected = "509f13f38e6ddaeac085632228deadc434573283a81c144f1c97f2e1e2245359"
if checksum != expected:
    raise SystemExit(f"Archive endommagée : SHA-256 inattendu {checksum}")
target = ASSETS / "Hunters Academy.png"
target.write_bytes(data)
print(f"Image originale restaurée : {target} ({len(data)} octets).")
