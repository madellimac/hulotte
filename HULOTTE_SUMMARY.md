# Hulotte - Synthèse et Architecture du Projet

## 1. Présentation Générale

**Hulotte** (*Hybrid Unified Libraries for Opensource TesTing of Embedded systems*) est un framework modulaire en C++17, SystemVerilog et Python conçu pour le prototypage rapide, la simulation, le test et la co-simulation matérielle/logicielle de chaînes de traitement de données (traitement du signal, codage de canal, blocs IP matériels).

Le projet s'appuie sur cinq piles technologiques principales :
1. **StreamPU** : Moteur d'exécution de graphes de tâches (dataflow) basé sur des sockets d'entrée/sortie.
2. **AFF3CT** : Bibliothèque de codage de canal (*Forward Error Correction* : Reed-Solomon, Polar, LDPC, BCH, etc.) intégrant StreamPU.
3. **Verilator** : Simulateur C++ pour SystemVerilog, permettant d'encapsuler des blocs IP matériels dans des tâches C++ StreamPU (*co-simulation logicielle/matérielle*).
4. **Boost ASIO / UART** : Pilotes de communication série pour échanger des trames de données avec des FPGA ou du matériel réel (*Hardware-in-the-Loop*).
5. **GUI Hulotte** (React/TypeScript/Vite + FastAPI) : Interface graphique optionnelle de supervision qui pilote le CLI existant sans le remplacer (création de projet, build, run, inspection du pipeline).

---

## 2. Structure de l'Arborescence

```text
hulotte/
├── framework/                  # Code du framework (seule source de vérité applicative)
│   ├── hulotte.py               # CLI graph-oriented (generate/build/init)
│   ├── create_project.py        # Générateur interactif/CLI historique + manifeste hulotte.project.json
│   ├── add_custom_module.py     # Ajoute un module C++ StreamPU personnalisé
│   ├── add_hardware_module.py   # Ajoute un bloc IP SystemVerilog (Verilator)
│   ├── add_uart_hw_module.py    # Ajoute un bloc IP enveloppé UART (FPGA)
│   ├── install_dependencies.py  # Installe/compile AFF3CT et StreamPU dans vendor/
│   ├── hulotte_utils.py         # Fonctions utilitaires partagées (ANSI, logs, sons, chemins)
│   ├── hulotte_gui.sh           # Lancement unifié de la GUI (backend FastAPI + frontend Vite)
│   ├── hulotte.txt, hulotte.wav # Assets de l'easter egg (ASCII art + hululement)
│   ├── pipeline.py, validation.py   # Modèle et validation du graphe de pipeline
│   ├── catalog.py, generator.py     # Chargement du catalogue et génération du C++
│   ├── project.py, paths.py         # Orchestration haut niveau et résolution des chemins
│   │
│   ├── templates/               # Gabarits Jinja2 (CMakeLists.txt.j2, main.cpp.j2, *.sv.j2, ...)
│   ├── catalog/modules.yaml      # Catalogue par défaut des modules (StreamPU/AFF3CT)
│   ├── common/                  # Composants hw/sw partagés copiés dans les projets générés
│   │   ├── sw/                   # Comparator, SerialPort, UartFrameIO, MySource
│   │   └── hw/                   # uart_recv, UART_fifoed_send_V1
│   ├── examples/project_config.example.json
│   │
│   └── gui/                     # Interface graphique optionnelle (ne remplace pas le CLI)
│       ├── backend/              # API FastAPI (main.py, api.py, services.py)
│       └── frontend/             # Application React + TypeScript + Vite
│
├── vendor/                     # Dépendances externes, installées localement (non trackées par git)
│   ├── streampu/                 # Moteur StreamPU (dataflow)
│   └── aff3ct/                   # Bibliothèque AFF3CT (avec StreamPU embarqué)
│
├── tests/                      # Non-régression
│   ├── unit/                     # Suite Python (test_*.py + fixtures/)
│   ├── integration/test.sh       # Matrice d'intégration (8 projets + idempotence add_*)
│   └── legacy_artifacts/         # Anciens projets générés committés, conservés pour référence
│
├── sandbox/                    # Bac à sable pour projets d'essai manuels (non tracké par git)
│
└── README.md, HULOTTE_SUMMARY.md, LICENSE, requirements.txt, .gitignore
```

Le framework ne copie ni ne dépend d'aucun fichier situé hors de `framework/` :
les dépendances externes (`vendor/`) et les projets utilisateurs (`sandbox/`,
ou tout répertoire externe passé via `--project-root`) restent séparés du code
applicatif.

---

## 3. Fonctionnement et Architecture Logicielle

### 3.1 Graphe de Tâches StreamPU
Une chaîne de traitement Hulotte est un graphe orienté de tâches déclenchées par la disponibilité des données sur leurs sockets :
- **Modules de source** (ex: `spu::module::Source_random`) : Génèrent les données d'entrée.
- **Modules de traitement C++** (ex: `MyModule`) : Héritent de `spu::module::Module` et définissent des tâches (`tsk`) et des sockets (`sck`).
- **Modules de codage AFF3CT** (ex: `Encoder_RS`, `Decoder_RS_std`) : Effectuent le codage/décodage canal.
- **Modules de simulation matérielle** (`VerilatorSimulation<VModel_...>`): Convertissent les vecteurs de données C++ en stimuli pour le modèle Verilator et récupèrent la réponse du bloc SystemVerilog.
- **Modules de communication UART** (`UartFrameIO`) : Transmettent et reçoivent les trames via port série Boost ASIO.
- **Modules de comparaison/vérification** (`Comparator`) : Comparent la voie sous test (*in_got*) avec la voie de référence (*in_ref*) et calculent le taux d'erreur binaire/trame (BER/FER).

### 3.2 Modèle d'Interface Matérielle Handshake (Ready/Valid)
Tous les blocs SystemVerilog générés par Hulotte respectent le protocole de contrôle de flux Ready/Valid :
- `in_data` / `out_data` : Bus de données.
- `in_val` / `out_val` : Signal indiquant que la donnée présente est valide.
- `in_rdy` / `out_rdy` : Signal indiquant que le récepteur est prêt à accepter une donnée.

### 3.3 Modes d'Exécution du Pipeline C++
1. **Minimal / Software-only** : Exécution purement logicielle C++ avec StreamPU (et éventuellement AFF3CT).
2. **HW-only (Co-simulation)** : Validation logicielle + modèle SystemVerilog simulé par Verilator.
3. **UART-only** : Communication série avec un équipement externe (ex: carte FPGA physique).
4. **Co-simulation hybride** : Comparaison en parallèle du modèle Verilator simulé et de l'implémentation FPGA réelle connectée sur UART.

---

## 4. Manifeste de Projet (`hulotte.project.json`)

Chaque projet généré contient un manifeste `hulotte.project.json` qui centralise les métadonnées et garantit l'idempotence des scripts :
- **`schema_version`** : Version du schéma (actuellement `1`).
- **`features`** : Drapeaux d'activation des fonctionnalités (`streampu`, `aff3ct`, `custom`, `hardware`, `uart_io`).
- **`uart`** : Configuration du port série (port, baudrate, taille de trame).
- **`pipeline.mode`** : Mode du pipeline (`minimal`, `hw_only`, `uart_only`, `co_simulation`).
- **`operations_log`** : Journal d'audit append-only enregistrant les commandes appliquées au projet (`create_project`, `add_custom_module`, etc.).

---

## 5. Guide des Scripts CLI

### 5.1 [install_dependencies.py](framework/install_dependencies.py)
Vérifie les prérequis système (g++, cmake, git), clone et compile les bibliothèques statiques :
- `libaff3ct*.a` dans `vendor/aff3ct/build/lib/`
- `libstreampu.a` dans `vendor/streampu/build/lib/`

### 5.2 [create_project.py](framework/create_project.py)
Crée un nouveau projet Hulotte.
```bash
# Exemple : Création d'un projet avec support matériel
python3 framework/create_project.py --name mon_projet --no-aff3ct --custom --hw --no-uart-io \
    --streampu-root /chemin/vers/vendor/streampu

# Validation d'un manifeste existant
python3 framework/create_project.py --validate-manifest /chemin/vers/mon_projet/hulotte.project.json
```

### 5.3 [add_custom_module.py](framework/add_custom_module.py)
Ajoute un module C++ StreamPU personnalisable dans `src/custom/` et met à jour `CMakeLists.txt` et `hulotte.project.json`.
```bash
./framework/add_custom_module.py --project-root /chemin/vers/projet --name FiltreGausien --id filtre_v1
```

### 5.4 [add_hardware_module.py](framework/add_hardware_module.py)
Ajoute un bloc SystemVerilog dans `src/hw/`. CMake compile automatiquement ce fichier avec Verilator pour créer une bibliothèque C++ liée au projet.
```bash
./framework/add_hardware_module.py --project-root /chemin/vers/projet --name FilterBlock --id filter_v1
```

### 5.5 [add_uart_hw_module.py](framework/add_uart_hw_module.py)
Génère un bloc IP SystemVerilog encapsulé avec la logique UART pour synthèse sur FPGA.
```bash
./framework/add_uart_hw_module.py --project-root /chemin/vers/projet --name UartFilter --id uart_filter_v1
```

### 5.6 [test.sh](tests/integration/test.sh)
Exécute la batterie de tests d'intégration dans un répertoire temporaire (génération d'une matrice de 8 projets, validation des manifestes, compilation CMake, exécution des exécutables et vérification de l'idempotence). Utiliser `HULOTTE_TEST_OUTPUT_DIR=/chemin` pour conserver les sorties à des fins de diagnostic.

---

## 6. Codes de Retour Standardisés des Scripts `add_*.py`
- `0` : Modification appliquée avec succès.
- `2` : Idempotent no-op (le module/id existe déjà avec la même définition).
- `1` : Erreur (ex: échec de validation, conflit de nom sans `--force`, fichier manquant).

---

## 7. GUI Hulotte (V1)

Une interface graphique optionnelle complète le CLI **sans le remplacer** : elle appelle les mêmes scripts (`create_project.py`, `build.sh`, binaires compilés) et utilise `hulotte.project.json` comme unique source de vérité (aucune configuration parallèle n'est stockée).

### 7.1 Lancement
```bash
./framework/hulotte_gui.sh
```
Démarre en une seule commande le backend FastAPI (`http://localhost:8000`, `--reload`) et le frontend Vite (`http://localhost:5173`, hot-reload). Chaque processus est lancé dans son propre groupe de processus (`setsid`) afin qu'un `Ctrl+C` arrête proprement uniquement les processus lancés par ce script, sans affecter d'autres instances Uvicorn/Vite indépendantes.

### 7.2 Architecture
- **Backend** ([gui/backend/](framework/gui/backend/)) : FastAPI + Uvicorn. `services.py` scanne le répertoire `sandbox/` à la racine du dépôt et, pour compatibilité legacy, `tests/legacy_artifacts/test_projects/`. La matrice `test.sh`, elle, utilise désormais un répertoire temporaire. Les logs et le statut (`idle`/`building`/`running`/`error`) sont conservés en mémoire par projet.
- **Frontend** ([gui/frontend/](framework/gui/frontend/)) : React + TypeScript + Vite, avec quatre panneaux principaux :
  - **ProjectPanel** : création de projet (formulaire) et sélection d'un projet existant.
  - **PipelinePanel** : affichage du pipeline sous forme de blocs cliquables ; un clic affiche les détails du module (id, type, `enabled`, fichiers source/wrapper/core) directement issus du manifeste.
  - **ActionsPanel** : boutons `Generate` / `Build` / `Run` / `Stop`.
  - **ConsolePanel** : affichage des logs en temps réel (polling 1s), défilement limité à la zone console.

### 7.3 API REST minimale
```
GET  /api/projects                    # Liste des projets (manifeste + pipeline_nodes)
POST /api/projects                    # Crée un projet (appelle create_project.py)
GET  /api/projects/{name}             # Détails d'un projet
POST /api/projects/{name}/generate    # Vérifie/recharge le manifeste
POST /api/projects/{name}/build       # Lance ./build.sh en tâche de fond
POST /api/projects/{name}/run         # Exécute le binaire compilé
POST /api/projects/{name}/stop        # Arrête le process build/run en cours
GET  /api/projects/{name}/status      # Statut courant
GET  /api/projects/{name}/logs        # Logs accumulés
```

### 7.4 Limites connues (V1)
- Pas d'édition d'un projet existant depuis la GUI (création uniquement) ; les modules (`add_custom_module.py`, `add_hardware_module.py`, `add_uart_hw_module.py`) ne sont pas encore pilotables depuis l'interface.
- Les logs sont conservés en mémoire côté backend (perdus au redémarrage d'Uvicorn).
- Le pipeline affiché reflète la présence des modules déclarés dans le manifeste, pas nécessairement leur câblage réel des sockets dans `main.cpp`.
