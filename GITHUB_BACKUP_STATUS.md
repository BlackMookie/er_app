# Sauvegarde GitHub — Ethereal Realms V15.1

Date : 19 novembre 2026.

Cette branche contient une sauvegarde du projet client/serveur V15.1 et les versions HTML historiques disponibles. Le client actuel se trouve dans `current/client/index.html` ; le serveur Python est dans `current/server.py`. Les fichiers `current/client/map.js`, `map.css` et `eardan-atlas.html` correspondent à **l'atlas de secours** : le module Map original et l'ensemble de ses fonctionnalités ne sont pas encore récupérés.

## Images

- `assets/ER_LOGO_EARDAN.png` est conservé directement, intact.
- L'image `assets/Hunters Academy.png` est conservée **sans aucune perte** en trois parties Base64 : `assets/Hunters_Academy.png.b64.part01` à `part03`. La liaison GitHub ne permettait pas de transférer directement ce fichier volumineux.
- Pour restaurer l'image exacte après un clone : `python scripts/restore_binary_assets.py`. Le script contrôle le SHA-256 avant d'écrire le PNG original.

## Données exclues

Les bases SQLite, comptes et données de personnages en cours sont volontairement absents du dépôt public. Les sauvegarder séparément dans un emplacement privé chiffré. Ne pas publier de jetons ni de fichiers `.env`.

## Contrôle

Le fichier `MANIFEST_SHA256.txt` contient les empreintes des fichiers d'origine, avant découpage de l'image. Le dépôt peut être vérifié après reconstruction avec `sha256sum -c MANIFEST_SHA256.txt` (dans un environnement disposant de sha256sum).

Le fichier `README.md` à la racine est conservé à l'identique en tant que document de l'archive locale initiale. Son ancienne mention « PAS encore poussée sur GitHub » est historique et n'indique pas le statut actuel.
