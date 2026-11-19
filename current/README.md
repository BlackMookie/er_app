# Ethereal Realms — Client & Serveur V15.1 (restauration carte)

Version de test multijoueur reposant sur **Ethereal Realms Craft V14.2**. Elle conserve la fiche, le Grimoire, l'historique, l'équipement, les dés, la gestion des runes et le Craft (plans, stock, finances, progression, projets, créations et renommée).

**Aucun compte externe n'est nécessaire.** Les comptes sont hébergés par **ton propre serveur**, avec stockage SQLite et sans base de données supplémentaire à installer.

## 1. Lancer sur Windows

Prérequis : **Python 3.10 ou supérieur** installé depuis python.org (cocher « Add Python to PATH ») ou via `py -3`.

- Double-cliquer sur `DEMARRER_WINDOWS_LOCAL.bat` pour tester **sur le PC qui héberge le serveur**.
- Puis, depuis un navigateur récent (Firefox, Chrome, Edge), ouvrir **http://127.0.0.1:8765**.
- Ne pas ouvrir directement `client/index.html` en double-cliquant dessus : le client a besoin des API du serveur.
- Laisser la fenêtre de commande ouverte pendant les tests. `Ctrl + C` arrête le serveur.

Les comptes, empreintes de mots de passe (scrypt avec sel aléatoire) et campagnes sont conservés dans `data/ethereal_realms.sqlite3`. La base est créée automatiquement au premier démarrage.

**Ne supprime pas ce fichier si tu souhaites conserver tes comptes et personnages.** Pour une sauvegarde simple, arrête le serveur, puis copie le dossier `data`.

## 2. Tester avec deux navigateurs sur le même PC

1. Ouvrir l'adresse ci-dessus dans Firefox. Créer le premier compte (identifiant de 3 à 32 caractères, mot de passe d'au moins 10 caractères).
2. Ouvrir la même adresse dans un **navigateur différent** ou dans une fenêtre privée séparée.
3. Pour tester le **même compte**, se connecter avec les mêmes identifiants ; les deux fenêtres ouvriront la même campagne.
4. Pour tester **deux comptes distincts**, créer un second compte. Sur le premier, cliquer sur **Compte & campagnes**, puis **Créer une invitation**. Transmettre le code au second compte, qui utilisera **Rejoindre une campagne**.
5. Dans une fenêtre, modifier un attribut, une information d'identité ou les finances du personnage : l'autre fenêtre se met à jour automatiquement. Essayer ensuite le catalogue **Craft → Matériaux & stock**, acheter du cuivre, puis consulter la bourse et le stock dans l'autre fenêtre.
6. Créer un plan dans **Craft → L'atelier**, l'enregistrer, puis vérifier qu'il apparaît dans la bibliothèque de plans de l'autre navigateur.

**Les campagnes sont séparées.** Les changements ne sont partagés qu'entre les membres d'une même campagne ; chaque compte possède à sa création sa propre campagne.

## 3. Tester entre deux PC ou à travers ton réseau local

1. Sur le PC qui héberge le serveur, double-cliquer sur **`DEMARRER_WINDOWS_RESEAU_LOCAL.bat`** au lieu du script local.
2. Taper `ipconfig` dans une fenêtre de commandes et noter l'**adresse IPv4 privée** du PC hébergeur (exemple : `192.168.1.42`).
3. Autoriser, si nécessaire, **Python / TCP 8765 en entrée sur le réseau privé uniquement** dans le pare-feu Windows.
4. Depuis le second PC, connecté au même réseau local, ouvrir `http://192.168.1.42:8765` en **remplaçant l'exemple par la véritable IP privée du serveur**.
5. Se connecter avec le même compte ou avec un second compte invité et refaire le test des modifications.

Tu peux également utiliser un VPN privé chiffré (par exemple Tailscale) pour rejoindre ton PC depuis l'extérieur, sans exposer directement le port 8765 au public. L'adresse à ouvrir sera alors l'IP privée du VPN du serveur, port `8765`.

**IMPORTANT — Sécurité Internet :** le serveur Python inclus sert à tester les fonctionnalités, pas à être exposé tel quel sur Internet. **N'ouvre pas/redirige pas le port 8765 sur ta box vers Internet.** Un accès public exige au minimum un reverse proxy HTTPS, une configuration réseau sécurisée et un durcissement des limites de requêtes / contrôles d'accès. En HTTP non chiffré, les identifiants et les données peuvent être interceptés sur un réseau non fiable.

## 4. Ce qui est réellement synchronisé

- L'identité, le portrait et les informations de la fiche du personnage.
- Les caractéristiques, compétences, bonus, runes et champs du Grimoire.
- Les ressources, la bourse commune **LE / PE / GE / CE**, les achats et l'inventaire.
- Les plans, le stock, les projets, la progression de craft, le registre de créations et la réputation artisanale.
- Les demandes de jets, le journal et le butin présents dans la fiche V14.2.

**Technologie :** JSON par chemins de champs avec vérification de la valeur précédente, SQLite transactionnel, flux **Server-Sent Events (SSE)** pour annoncer les nouvelles versions et interrogation périodique de secours toutes les 3,5 secondes. Le client conserve une file d'écritures locales temporaires en cas d'interruption et les rejoue lorsque la connexion revient. Un conflit sur le même champ bloque l'écrasement silencieux et propose un **export de la copie locale** avant rechargement.

**Limites importantes de cette version :**

- La structure actuelle de l'application reste centrée sur **une fiche de personnage active par campagne**. Les comptes peuvent partager cette fiche, mais l'attribution individuelle de personnages et les rôles MJ/joueur détaillés ne sont pas encore implémentés.
- Les jets aléatoires et les issues du Craft sont encore déterminés par le **client**, comme dans V14.2 ; la base centrale en reçoit le résultat. Ce prototype n'a donc pas de dispositif anti-triche ou de validation MJ côté serveur. Pour une campagne compétitive, il faudra migrer la résolution des jets sensibles vers le serveur.
- Les éléments graphiques personnalisés importés localement (fond ou logo) restent propres au navigateur, sauf ceux déjà intégrés au HTML. Le portrait du personnage, lui, appartient à la fiche répliquée.
- **Carte d’Eardan restaurée sous forme d’atlas de secours** : le paquet contient désormais `map.js`, `map.css` et `eardan-atlas.html`, une ancienne version de l’atlas interactif récupérée. Le zoom, la recherche, les vues Relief/Nations/Factions, l’hydrographie, les nouveaux repères, les fiches de lieux, les plans urbains détaillés et l’export PNG sont accessibles. Les corrections Nescya/Hakkeshu/Mushis/Fenris/Gaorens/Rohkans sont incluses. **Ce n’est pas une récupération du module Map original** : son code exact et les fonctionnalités spécifiques non incluses dans cet atlas n’étaient pas présents dans le HTML fourni. La vue de l’atlas n’est pas synchronisée entre joueurs.
- Les fichiers de cette version ne contiennent pas une synchronisation multijoueur de l'intégralité des futurs modules JdR (routes commerciales, propriétés et alliances) qui ne sont pas encore développés.

## 5. Importer une ancienne sauvegarde locale V14.2

La V14.2 enregistrait sa fiche dans le `localStorage` du navigateur. Ce stockage appartient à l'origine de l'ancien fichier et **ne peut pas être lu automatiquement** par le nouveau serveur HTTP.

Pour importer tes données réelles :

1. Ouvre **l'ancien fichier HTML V14.2** dans le navigateur qui contient la fiche enregistrée.
2. Ouvre les outils de développement (`F12` → **Console**).
3. Copie-colle le petit script de `EXPORTER_SAUVEGARDE_LOCALE.txt` dans cette console et valide. Il télécharge un JSON **sans modifier ta sauvegarde**. Selon le navigateur, il faut d'abord autoriser explicitement le collage dans la console.
4. Dans le client V15, connecte-toi, ouvre **Compte & campagnes**, puis **Importer une sauvegarde JSON dans une nouvelle campagne** et sélectionne le fichier exporté.

Cette importation **crée une nouvelle campagne**, sans écraser ta campagne actuelle. Tu peux également exporter à tout moment une campagne V15 depuis **Compte & campagnes → Exporter cette fiche (JSON)**.

## 6. Questions courantes

**Un second PC ne peut pas ouvrir la page** — Vérifie que le script réseau est lancé, que les deux PC sont sur le bon réseau, que l'IP est bien celle du serveur et que le pare-feu privé autorise TCP 8765. Ne saisis pas l'adresse `0.0.0.0` dans ton navigateur.

**Les modifications ne se mettent pas à jour** — Vérifie que les deux fenêtres ont sélectionné la **même campagne**, puis regarde le statut de synchronisation en haut. Le flux SSE est complété par une récupération automatique. Si les changements restent « en attente », vérifie la connexion au serveur.

**Un conflit apparaît** — Cela signifie que deux sessions ont modifié la même valeur avant synchronisation. Exporte la version locale depuis le panneau de conflit, puis recharge la version du serveur si tu acceptes d'annuler les changements en attente.

**La carte ne s’affiche pas** — Vérifie que les trois fichiers `client/map.js`, `client/map.css` et `client/eardan-atlas.html` sont présents. La navigation « Carte d’Eardan » apparaît dès qu’une campagne est chargée. Le module cartographique original n’est pas inclus : cette V15.1 fournit un atlas de secours.

**J'ai perdu mon mot de passe** — Cette V15 ne comprend pas encore d'interface de récupération des identifiants ; conserve les mots de passe de test.

## 7. Fichiers livrés

- `client/index.html` : la fiche V14.2 et le Craft, avec comptes, campagnes et réplication intégrés.
- `client/map.js` + `map.css` + `eardan-atlas.html` : adaptateur et atlas interactif autonome de secours.
- `server.py` : API HTTP, comptes, invitations, SQLite, résolution des conflits et SSE (bibliothèque standard Python uniquement).
- `DEMARRER_WINDOWS_LOCAL.bat` : serveur limité au PC local.
- `DEMARRER_WINDOWS_RESEAU_LOCAL.bat` : serveur visible sur le réseau privé (pare-feu à vérifier).
- `EXPORTER_SAUVEGARDE_LOCALE.txt` : migration de ton stockage de la version HTML précédente.
- `data/` : base SQLite créée au premier démarrage.

*Cette V15 est un environnement de validation et de développement ; elle n'est pas encore un serveur de production public.*