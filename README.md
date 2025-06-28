# Tresoperso

Tresoperso est une application de gestion de trésorerie personnelle. Elle permet d'importer des relevés bancaires au format CSV, de catégoriser les transactions et de visualiser l'évolution de vos dépenses et recettes.

## Fonctionnalités prévues

- Import des transactions depuis des fichiers CSV
- Détection des doublons lors de l'import
- Attribution de catégories et sous-catégories aux transactions
- Affichage des transactions dans un tableau filtrable
- Graphiques d'analyse (donut, Sankey)
- Projection de trésorerie basée sur l'historique

## Lancement rapide

Un serveur Flask minimal est fourni pour servir l'application Web locale. Assurez-vous d'avoir **Python&nbsp;3** installé.

Avant le premier démarrage, installez les dépendances du projet&nbsp;:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
python run.py
```

Par défaut, l'application s'ouvrira automatiquement dans votre navigateur à l'adresse http://localhost:5000/.
Si ce n'est pas le cas, ouvrez manuellement cette URL.
Le serveur Flask écoute sur l'adresse `0.0.0.0`, ce qui permet d'exposer
l'application sur le réseau local.

## Environnement de développement

Les dépendances principales (**Flask**, **SQLAlchemy**, **Flask-Login**) ainsi que
**pytest** pour les tests sont listées dans `requirements-dev.txt`. Installez-les
pour disposer d'un environnement complet :

```bash
pip install -r requirements-dev.txt
```

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

Le fichier `tresoperso.db` est placé dans le répertoire courant et peut être
supprimé en cas de réinitialisation souhaitée.

## Gestion des comptes et import CSV

Depuis l'onglet **Comptes** de l'interface web vous pouvez gérer plusieurs comptes bancaires.
Chaque import CSV crée automatiquement le compte correspondant s'il n'existe pas encore.
Si le numéro et le type correspondent à un compte existant, la date d'export est simplement mise à jour au lieu de créer un doublon.
Utilisez le bouton «Importer CSV» pour sélectionner un fichier et mettre à jour le compte choisi. Un bouton «Supprimer» permet aussi d'effacer un compte.

## Tests

Les dépendances de développement nécessaires à l'exécution de la suite se
trouvent dans `requirements-dev.txt`. Installez-les impérativement avant de
lancer les tests :

```bash
pip install -r requirements-dev.txt
# ou ./install-dev-deps.sh
```

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

La bibliothèque JavaScript **Chart.js** est chargée depuis le CDN jsDelivr
(`https://cdn.jsdelivr.net`) et **Plotly** depuis `https://cdn.plot.ly`.
Une connexion Internet est donc requise pour afficher correctement les
graphiques de l'interface.

## Licence

Ce projet est distribué sous licence MIT. Voir le fichier [LICENSE](LICENSE).
