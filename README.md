# Tresoperso

Tresoperso est une application de gestion de trésorerie personnelle. Elle permet d'importer des relevés bancaires au format CSV, de catégoriser les transactions et de visualiser l'évolution de vos dépenses et recettes.

## Fonctionnalités prévues

- Import des transactions depuis des fichiers CSV
- Détection des doublons lors de l'import
- Attribution de catégories et sous-catégories aux transactions
- Affichage des transactions dans un tableau filtrable
- Graphiques d'analyse (donut, Sankey)
- Projection de trésorerie basée sur l'historique
- Visualisation du flux de trésorerie
- Tableau de bord filtrable sur les favoris

La page **Flux de trésorerie** affiche les opérations récurrentes détectées sur les six
derniers mois. Les libellés des transactions sont prétraités (suppression des
chiffres, des espaces et de la ponctuation) puis comparés avec un seuil de
similarité de 80&nbsp;%. Deux transactions ou plus sont groupées lorsque ce seuil
est atteint et que leurs montants restent entre 80&nbsp;% et 130&nbsp;% de la
moyenne du groupe. La détection est désormais plus souple&nbsp;: la contrainte
sur l'écart en jours entre deux occurrences a été supprimée afin de prendre en
compte les prélèvements dont la date varie légèrement d'un mois à l'autre.

Un sélecteur de mois permet de choisir la période à afficher. Les boutons « Calendrier » et « Liste/anneau » basculent respectivement entre la vue calendrier et une liste accompagnée d'un graphique en anneau. Les boutons en tête de section affichent soit l'ensemble des flux, soit uniquement les entrées, les sorties ou le solde pour le mois choisi.

## Tableau de bord

Cette section offre une vue synthétique des dépenses et des recettes. Un nouveau bouton « Analyser uniquement les transactions favorites » permet de limiter les calculs aux opérations marquées comme favorites. Désactivez-le pour revenir à l'ensemble des transactions. Le backend expose la route `/dashboard` qui accepte le paramètre `favorites_only` (par exemple `/dashboard?favorites_only=true`) pour obtenir les mêmes informations via l'API.

## Lancement rapide

Un serveur Flask minimal est fourni pour servir l'application Web locale. Assurez-vous d'avoir **Python&nbsp;3** installé.

Avant le premier démarrage, installez les dépendances du projet&nbsp;:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
python run.py
```

Ces commandes ont besoin d'un accès Internet pour télécharger les dépendances. Utilisez un environnement préparé en cas d'absence de réseau.
Par défaut, l'application s'ouvrira automatiquement dans votre navigateur à l'adresse http://localhost:5000/.
Si ce n'est pas le cas, ouvrez manuellement cette URL.
Le serveur Flask écoute sur l'adresse `0.0.0.0`, ce qui permet d'exposer
l'application sur le réseau local.

Le cookie de session n'est plus marqué comme sécurisé par défaut. Il est donc
accepté même en HTTP simple sans configuration supplémentaire.

## Thèmes disponibles

L'interface propose plusieurs feuilles de style sélectionnables depuis le menu
« Paramètres ». Les thèmes intégrés correspondent aux fichiers CSS suivants :

```
light.css
dark.css
flat-light.css
flat-dark.css
luxury-light.css
luxury-dark.css
magazine-light.css
magazine-dark.css
```

Choisissez simplement le nom de thème désiré dans la liste pour appliquer la
mise en forme associée.

## Environnement de développement

Les dépendances principales (**Flask**, **SQLAlchemy**, **Flask-Login**) ainsi que
**pytest** pour les tests sont listées dans `requirements-dev.txt`. Installez-les
pour disposer d'un environnement complet :

```bash
pip install -r requirements-dev.txt
```
Ces paquets sont récupérés en ligne, prévoyez donc un accès réseau ou un environnement déjà préparé.

## Base de données

Le backend repose sur **SQLAlchemy** avec une base SQLite créée dans le
fichier `tresoperso.db`. Lors du premier démarrage, les tables ainsi qu'un
compte administrateur `admin` (mot de passe `admin`) sont générés
automatiquement.
Les catégories et sous-catégories sont également synchronisées depuis le fichier
`backend/categories.json` à chaque démarrage.

```bash
python run.py
```

Par défaut, la base SQLite est stockée dans `tresoperso.db` à la racine du
projet. L'application y accède via un chemin absolu afin que le même fichier
soit utilisé même si `run.py` est lancé depuis un autre répertoire. Ce fichier
peut être supprimé pour réinitialiser l'état du programme.

## Gestion des comptes et import CSV

Depuis l'onglet **Comptes** de l'interface web vous pouvez gérer plusieurs comptes bancaires.
Chaque import CSV crée automatiquement le compte correspondant s'il n'existe pas encore.
Si le numéro et le type correspondent à un compte existant, la date d'export est simplement mise à jour au lieu de créer un doublon.
Utilisez le bouton «Importer CSV» pour sélectionner un fichier et mettre à jour le compte choisi. Un bouton «Supprimer» permet aussi d'effacer un compte.

## API

Le backend expose plusieurs routes JSON consommées par l'interface web. La route
`/stats/recurrents/summary` fournit par exemple le total des montants positifs,
négatifs, le solde global (y compris les soldes initiaux des comptes) et le
montant cumulé des dépenses récurrentes détectées pour le mois demandé. La
route `/dashboard` accepte quant à elle le paramètre `favorites_only=true` pour
retourner uniquement les transactions favorites.

## Tests

Les dépendances de développement nécessaires à l'exécution de la suite se trouvent dans `requirements-dev.txt`.
**Important : installez-les avant toute exécution de tests.** Utilisez :
```bash
pip install -r requirements-dev.txt
# ou ./install-dev-deps.sh
```
Ces commandes téléchargent les paquets depuis Internet : prévoyez un accès réseau ou un environnement préparé.

Les tests s'appuient sur **pytest**. Une fois l'environnement prêt, exécutez :

```bash
pytest
```

## Format des fichiers CSV

Pour la BNP, les champs du CSV doivent être séparés par des point‑virgules (`;`).
La première ligne décrit le compte bancaire sous la forme :
`type de compte ; nom ; numéro ; date du fichier ; ; solde à la date`.
La seconde ligne est vide et la troisième contient les en‑têtes :
`Date opération ; Libellé court ; Type opération ; Libellé opération ; Montant opération en euro`.
Les lignes suivantes contiennent les opérations au même ordre que ces en‑têtes.
Les colonnes `type opération` et `libellé court` sont enregistrées dans la base pour chaque opération.

Les montants peuvent contenir un espace comme séparateur de milliers et
utiliser soit la virgule soit le point pour indiquer les décimales.


Problèmes courants :

- Fichiers délimités par des virgules `;`
- Colonnes séparées `debit`/`credit` au lieu d'une seule colonne `montant`

## Packaging macOS

Pour créer un exécutable autonome pour macOS, PyInstaller est utilisé. Un
`Makefile` fournit la cible suivante :

```bash
make package
```

Cette commande lance `pyinstaller --onefile --add-data "frontend:frontend" run.py`
et génère le binaire dans `dist/run`. La construction doit être effectuée sur
macOS afin d'obtenir un
exécutable natif.

Les bibliothèques JavaScript **Chart.js** et **Plotly** sont désormais
fournies localement dans le dossier `frontend/libs/`.
L'application n'a donc plus besoin d'accès Internet pour afficher les
graphiques de l'interface.

## Licence

Ce projet est distribué sous licence MIT. Voir le fichier [LICENSE](LICENSE).
