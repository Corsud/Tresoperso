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
python run.py
```

Par défaut, l'application s'ouvrira automatiquement dans votre navigateur à l'adresse http://localhost:5000/.
Si ce n'est pas le cas, ouvrez manuellement cette URL.
Le serveur Flask écoute sur l'adresse `0.0.0.0`, ce qui permet d'exposer
l'application sur le réseau local.

## Base de données

Le backend repose sur **SQLAlchemy** avec une base SQLite créée dans le
fichier `tresoperso.db`. Lors du premier démarrage, les tables ainsi qu'un
compte administrateur `admin` (mot de passe `admin`) sont générés
automatiquement.

```bash
python run.py
```

Le fichier `tresoperso.db` est placé dans le répertoire courant et peut être
supprimé en cas de réinitialisation souhaitée.

## Format des fichiers CSV

Pour la BNP : Les champs du CSV doivent être séparés par des point-virgules (`;`). 
Les fichiers de la bnp ne comportent pas d'entete de colonnes. la premiere ligne decrit le compte bancaire. A partir de la deuxieme ligne se trouvent les transactions.
Elles sont au format :`date`, `type de transaction`,`moyen de paiement`,`libellé` et
`montant`.


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

## Licence

Ce projet est distribué sous licence MIT. Voir le fichier [LICENSE](LICENSE).
