# Migration vers la fiche V14.52 — client/serveur

La fiche locale validée le 20 novembre 2026 est la **V14.52** (environ 9 Mo avec illustrations intégrées). Le backend déjà présent dans `current/server.py` expose comptes, campagnes, invitations, stockage SQLite, patchs concurrents et événements SSE.

Le fichier complet `client/index.html` doit être remplacé par la version V14.52 adaptée au serveur avant lancement. **Le dépôt ne contient pas encore ce remplacement** : ne pas présenter l'ancien `current/client/index.html` comme V14.52.

Pour déployer le paquet V14.52 client/serveur fourni séparément :

1. Télécharger ce dépôt (ZIP ou `git clone`).
2. Copier le fichier `index.html` du paquet dans `current/client/index.html` en remplaçant l'ancien.
3. Exécuter `current/DEMARRER_WINDOWS_LOCAL.bat` sur Windows.
4. Ouvrir `http://127.0.0.1:8765`, créer un compte et choisir la campagne.
5. Pour deux appareils : utiliser `DEMARRER_WINDOWS_RESEAU_LOCAL.bat` sur le PC serveur et ouvrir depuis l'autre PC l'IP privée du serveur sur le port 8765. Ne pas exposer ce serveur directement sur Internet.

**Attention** : la base SQLite `current/data/ethereal_realms.sqlite3` est une donnée d'exécution, non suivie par Git. GitHub ne sauvegarde donc **pas les personnages ni les comptes** ; les sauvegarder séparément en arrêtant le serveur. Avant tout déploiement distant public, ajouter HTTPS et durcir l'authentification et la gestion des sessions.

Le mode synchronisation V14.52 reste un prototype à valider en deux navigateurs ; éviter les modifications concurrentes sur un même champ jusqu'à validation des conflits et de l'interface.
