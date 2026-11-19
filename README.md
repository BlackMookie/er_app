# Ethereal Realms — sauvegarde Git prête à déposer

**Statut : sauvegarde locale préparée, PAS encore poussée sur GitHub.**

## Version actuelle

- `current/` : **V15.1 Client/Serveur** (Python standard library + SQLite), Craft V14.2, carte d’Eardan restaurée sous forme d’atlas de secours.
- `current/client/index.html` : client, UI, Grimoire, Craft, personnages, connexion.
- `current/client/map.js`, `map.css`, `eardan-atlas.html` : module cartographique de secours. **Le code du Map original n’a pas été retrouvé**, son ensemble de fonctionnalités n’est donc pas restauré à l’identique.
- `current/server.py` : API d'inscription/connexion, gestion des campagnes, synchronisation HTTP/SSE, SQLite.
- `current/README.md` : guide de lancement Windows, LAN, VPN privé, limites de sécurité et test multijoueur.

## Éléments conservés

- `history/` : copies HTML des versions disponibles, de la fiche locale au Craft V14.2.
- `assets/` : logo Eardan et image d’Académie, fournis dans le contexte du projet.
- `dev-tools/` : scripts disponibles pour la récupération et vérification du module Map.
- `MANIFEST_SHA256.txt` : empreintes de tous les fichiers sauvegardés.

## Sécurité / données

Ce paquet **n'inclut aucune base SQLite de test ou de joueurs**, aucun cookie de session, aucun mot de passe, et aucun fichier d'environnement. Les comptes, personnages et campagnes créés sur ton PC résident dans **`current/data/ethereal_realms.sqlite3`**, qui est volontairement exclu de Git par `.gitignore`. Sauvegarde séparément `data/` dans un stockage privé si tu souhaites préserver les données réelles.

## Sauvegarde GitHub

Une fois le dépôt `er_app` réellement autorisé dans la connexion GitHub, ce dossier pourra être commité dans une branche dédiée sans écraser le dépôt préexistant. Vérifier son contenu et ne pas le mettre en public si des documents internes y sont ajoutés.