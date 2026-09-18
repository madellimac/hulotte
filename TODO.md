générer un catalog  large en parsant AFF3CT et STREAMPU
pourquoi le catalog est copié dans chaque projet



## Plan : Installation Hulotte et intégration GUI

Mettre en place une commande globale `hulotte`, mémoriser le chemin de StreamPU une seule fois, puis faire utiliser la même API par le CLI et le GUI. Le workflow legacy sera conservé pendant la migration.

**Étapes**

1. **Créer la configuration centralisée**
   - Ajouter `framework/config.py`.
   - Stocker la configuration dans `~/.config/hulotte/config.yaml` selon XDG.
   - Définir l’ordre de priorité : option explicite, configuration projet, configuration utilisateur, variable d’environnement, chemins standards.
   - Valider automatiquement la présence de `include/streampu.hpp` et `build/lib/libstreampu.a`.
   - Produire des erreurs claires lorsque StreamPU est absent ou invalide.

2. **Ajouter l’installation Python**
   - Créer `pyproject.toml`.
   - Exposer la commande globale `hulotte`.
   - Permettre l’utilisation depuis n’importe quel répertoire, sans `PYTHONPATH`.
   - Conserver `python -m framework.hulotte` pour les tests et le développement.

3. **Ajouter les commandes de configuration**
   - Implémenter :
     - `hulotte config show`
     - `hulotte config set streampu-root <chemin>`
     - `hulotte config unset streampu-root`
   - Garder `--hulotte-root` et `--streampu-root` comme options avancées.
   - Faire fonctionner le parcours principal :

   ```text
   hulotte init mon_projet
   cd mon_projet
   hulotte generate
   hulotte build
   ```

4. **Brancher le résolveur dans l’API projet**
   - Modifier [framework/project.py](PROJECTS/hulotte/framework/project.py) pour utiliser la configuration centralisée.
   - Adapter `init_project()`, `generate_project()` et `build_project()`.
   - Préserver les appels avec chemins explicites afin de ne pas casser les tests ni les utilisateurs avancés.
   - Enregistrer dans `hulotte.project.yaml` les dépendances résolues du projet.

5. **Migrer progressivement le backend GUI**
   - Adapter [framework/gui/backend/services.py](PROJECTS/hulotte/framework/gui/backend/services.py) pour ne plus dépendre uniquement de `REPO_ROOT/vendor/streampu`.
   - Ajouter la lecture de la configuration utilisateur et l’affichage de l’état de StreamPU.
   - Ajouter un chemin spécifique aux projets graph basés sur `pipeline.yaml`.
   - Modifier [framework/gui/backend/api.py](PROJECTS/hulotte/framework/gui/backend/api.py) pour exposer :
     - la configuration ;
     - la détection de StreamPU ;
     - la création/génération/build d’un projet graph.
   - Conserver le workflow legacy basé sur `create_project.py`, `hulotte.project.json` et `build.sh`.

6. **Ajouter les tests et la documentation**
   - Étendre [tests/unit/test_cli.py](PROJECTS/hulotte/tests/unit/test_cli.py).
   - Ajouter des tests dédiés à la configuration et à la résolution des chemins.
   - Tester `pip install .`, puis `hulotte --help` depuis un dossier extérieur.
   - Vérifier `init`, `generate` et `build` avec la fixture minimale.
   - Tester que les projets legacy du GUI continuent de fonctionner.
   - Mettre à jour [WORKFLOW.md](PROJECTS/hulotte/WORKFLOW.md), [README.md](PROJECTS/hulotte/README.md), [INSTALL_INFO.txt](PROJECTS/hulotte/INSTALL_INFO.txt) et [workflow_summary.md](PROJECTS/hulotte/workflow_summary.md).

**Fichiers principaux**

- [framework/hulotte.py](PROJECTS/hulotte/framework/hulotte.py) : CLI et nouvelles sous-commandes.
- [framework/project.py](PROJECTS/hulotte/framework/project.py) : orchestration des projets.
- [framework/gui/backend/services.py](PROJECTS/hulotte/framework/gui/backend/services.py) : intégration GUI.
- [framework/gui/backend/api.py](PROJECTS/hulotte/framework/gui/backend/api.py) : endpoints GUI.
- [framework/catalog.py](PROJECTS/hulotte/framework/catalog.py) et [framework/paths.py](PROJECTS/hulotte/framework/paths.py) : résolution existante à réutiliser.
- Nouveau [pyproject.toml](PROJECTS/hulotte/pyproject.toml).
- Nouveau [framework/config.py](PROJECTS/hulotte/framework/config.py).

**Vérification**

1. Installer Hulotte dans un environnement virtuel temporaire avec `pip install .`.
2. Vérifier `hulotte --help` depuis `/tmp`.
3. Configurer StreamPU avec `hulotte config set`.
4. Créer puis générer un projet sans chemin explicite.
5. Compiler la fixture StreamPU si les bibliothèques sont disponibles.
6. Vérifier dans le GUI un projet graph et un projet legacy existant.

**Décisions**

- Pas de téléchargement automatique de StreamPU dans la première version.
- Hulotte est découvert automatiquement depuis son installation.
- StreamPU est configuré une seule fois, avec possibilité de surcharge.
- Le workflow legacy reste supporté pendant la migration.
- Le CLI et le GUI réutilisent la même API Python de configuration et d’orchestration.


