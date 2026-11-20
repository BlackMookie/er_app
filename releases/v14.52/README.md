# Ethereal Realms — v14.52 Client / Serveur

**Base UI conservée : v14.51.** Les modules Map, Craft, Grimoire, gestion des PC, fiches de races et compétences restent intégrés dans `client/index.html`.

## Installation et démarrage

Prérequis : **Python 3.10+**, sans bibliothèque Python additionnelle.

1. Extraire l'archive ZIP dans un dossier local.
2. Double-cliquer sur `DEMARRER_WINDOWS_LOCAL.bat`.
3. Ouvrir `http://127.0.0.1:8765` dans Firefox ou Chrome.
4. Créer un compte (mot de passe de 10 caractères minimum), puis une campagne.
5. Pour tester un deuxième compte, choisir **Campagnes → Créer un code d'invitation** avec le compte MJ. Se connecter dans une fenêtre privée ou un navigateur différent, puis utiliser **Rejoindre une campagne**.

**Ne pas** ouvrir `client/index.html` directement : la version client/serveur nécessite une API disponible.

## Données et migration

Le navigateur conserve toujours une copie locale de la fiche v14.51. Une fois connecté, choisir **Importer ma fiche v14.51 locale** pour envoyer explicitement cette copie au serveur. Le serveur ne l'importe jamais automatiquement, et l'utilisateur peut créer une campagne vierge à la place.

**Attention :** si l'ancienne fiche a été ouverte via `file://`, son stockage peut ne pas être accessible sous `http://127.0.0.1:8765`, car `localStorage` est isolé par origine. Dans ce cas, il faut migrer les données de l'ancien navigateur via export/import JSON. N'utilisez pas la nouvelle campagne pour écraser une ancienne sauvegarde non exportée.

Le serveur crée `data/er.sqlite3` automatiquement. **Ne jamais publier ce fichier sur GitHub** (comptes et campagnes). Pour le sauvegarder, arrêter le serveur et copier tout le dossier `data/` sur un disque privé.

## Synchronisation

- Fiche, attributs, compétences, runes et Craft : stockage JSON de campagne en SQLite.
- Carte : repères, tracés et filtres enregistrés dans la campagne (état partagé).
- Changement détecté et transmis automatiquement, avec interrogation serveur toutes les ~2,3 secondes. Les autres navigateurs voient les modifications **sans rechargement complet**.
- Contrôle des collisions sur la valeur antérieure de chaque champ. Si deux personnes modifient le **même** champ, le serveur refuse l'écrasement silencieux : exporter la copie locale ou recharger la version distante.
- Côté serveur, seules les sessions MJ peuvent attribuer des PC de session ou écrire les annotations de Map.
- Les autres champs d'une campagne partagée restent éditables par ses membres, dans cette version de test.

**Statut : prototype**, pas encore un hébergement Internet public durci. Les événements ne sont pas gérés par WebSockets : le client utilise une file de modifications et une interrogation périodique. Les dépenses de PC du joueur sont contrôlées dans l'UI, mais le serveur n'impose pas encore toutes les règles métiers. Les résultats de Craft et les dés restent calculés côté client. Les mises à jour simultanées d'une même liste peuvent entrer en conflit.

## Test à distance via VPN privé

1. Lancer `DEMARRER_WINDOWS_RESEAU_PRIVE.bat` sur le PC hôte.
2. Autoriser le port TCP **8765** uniquement sur le réseau privé / VPN dans le pare-feu.
3. Depuis l'autre PC, ouvrir `http://IP_PRIVEE_DU_SERVEUR:8765` dans un navigateur.
4. Les deux personnes utilisent des comptes différents dans une campagne partagée.

**Ne pas ouvrir de redirection de port 8765 sur une box Internet.** L'application utilise HTTP pour ses tests ; utiliser un VPN privé chiffré (par exemple Tailscale) pour un test entre domiciles. Une publication sur Internet nécessite reverse proxy HTTPS, quotas, authentification renforcée, journaux et revue de sécurité.

## Sauvegarde GitHub

Sur la branche `backup/v14.52-client-serveur`, le dossier `releases/v14.52/archive-parts/` contient 18 fragments Base64 de l’archive complète.

Pour récupérer exactement le ZIP et tous ses fichiers à partir du dépôt GitHub :

```console
python releases/v14.52/reconstruct_from_github.py
```

L’empreinte SHA-256 attendue est `f4713bd53eb9ea11fa43e3138d813324dd64ee07aedd6db25d228805ee3a0781`. La reconstruction s’arrête si l’un des fragments manque ou si le contenu a été altéré.