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

```bash
pip install -r requirements.txt
python3 run.py
```

Par défaut, l'application s'ouvre automatiquement dans votre navigateur à l'adresse http://localhost:5000/.

## Licence

Ce projet est distribué sous licence MIT. Voir le fichier [LICENSE](LICENSE).
