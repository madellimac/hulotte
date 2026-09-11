# Hulotte - Synthèse et Architecture du Projet

## 1. Présentation Générale

**Hulotte** (*Hybrid Unified Libraries for Opensource TesTing of Embedded systems*) est un framework modulaire en C++17, SystemVerilog et Python conçu pour le prototypage rapide, la simulation, le test et la co-simulation matérielle/logicielle de chaînes de traitement de données (traitement du signal, codage de canal, blocs IP matériels).

Le projet s'appuie sur quatre piles technologiques principales :
1. **StreamPU** : Moteur d'exécution de graphes de tâches (dataflow) basé sur des sockets d'entrée/sortie.
2. **AFF3CT** : Bibliothèque de codage de canal (*Forward Error Correction* : Reed-Solomon, Polar, LDPC, BCH, etc.) intégrant StreamPU.
3. **Verilator** : Simulateur C++ pour SystemVerilog, permettant d'encapsuler des blocs IP matériels dans des tâches C++ StreamPU (*co-simulation logicielle/matérielle*).
4. **Boost ASIO / UART** : Pilotes de communication série pour échanger des trames de données avec des FPGA ou du matériel réel (*Hardware-in-the-Loop*).

---

## 2. Structure de l'Arborescence

```text
hulotte/
├── create_project.py          # Générateur interactif et CLI de nouveaux projets Hulotte
├── add_custom_module.py       # Script d'ajout de modules C++ StreamPU personnalisés
├── add_hardware_module.py     # Script d'ajout de blocs IP SystemVerilog (Verilator)
├── add_uart_hw_module.py      # Script d'ajout de blocs IP enveloppés UART (FPGA)
├── install_dependencies.py    # Script d'installation automatique d'AFF3CT et StreamPU
├── hulotte_utils.py           # Fonctions utilitaires partagées (ANSI, logs, sons, paths)
├── test.sh                    # Suite de tests d'intégration et de non-régression
├── README.md                  # Documentation utilisateur
├── project_config.example.json# Exemple de fichier de configuration de projet
│
├── templates/                 # Squelettes Jinja2 utilisés par les scripts de génération
│   ├── CMakeLists.txt.j2      # Modèle CMake avec détection automatique Verilator & StreamPU
│   ├── main.cpp.j2            # Squelette C++ d'instanciation et de binding du graphe de tâches
│   ├── MyModule.hpp.j2 / .cpp.j2 # Modèle de module C++ StreamPU
│   ├── hw_module.sv.j2        # Modèle de bloc IP SystemVerilog (handshake Ready/Valid)
│   ├── uart_hw_module.sv.j2   # Modèle de bloc IP encapsulé avec interface UART
│   ├── Top_Level.sv.j2        # Top-level SystemVerilog pour synthèse/FPGA
│   ├── VerilatorSimulation.hpp.j2 # Wrapper C++ adaptant un modèle Verilator en tâche StreamPU
│   ├── view_waves.sh.j2       # Script de visualisation des chronogrammes (.vcd/.fst)
│   └── README.md.j2           # Documentation générée dans chaque nouveau projet
│
├── Common/streampu/           # Composants réutilisables partagés
│   ├── sw/                    # Composants logiciels C++ (Comparator, SerialPort, UartFrameIO, MySource)
│   └── hw/                    # Composants matériels SystemVerilog (uart_recv, UART_fifoed_send_V1)
│
├── aff3ct/                    # Sous-module git / dépôt AFF3CT (avec StreamPU embarqué)
├── streampu/                  # Sous-module git / dépôt StreamPU autonome
└── test_projects/             # Projets générés automatiquement par test.sh pour validation
```

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

### 5.1 [install_dependencies.py](install_dependencies.py)
Vérifie les prérequis système (g++, cmake, git), clone et compile les bibliothèques statiques :
- `libaff3ct*.a` dans `aff3ct/build/lib/`
- `libstreampu.a` dans `streampu/build/lib/`

### 5.2 [create_project.py](create_project.py)
Crée un nouveau projet Hulotte.
```bash
# Exemple : Création d'un projet avec support matériel
python3 create_project.py --name mon_projet --no-aff3ct --custom --hw --no-uart-io \
    --streampu-root /chemin/vers/streampu

# Validation d'un manifeste existant
python3 create_project.py --validate-manifest /chemin/vers/mon_projet/hulotte.project.json
```

### 5.3 [add_custom_module.py](add_custom_module.py)
Ajoute un module C++ StreamPU personnalisable dans `src/custom/` et met à jour `CMakeLists.txt` et `hulotte.project.json`.
```bash
./add_custom_module.py --project-root /chemin/vers/projet --name FiltreGausien --id filtre_v1
```

### 5.4 [add_hardware_module.py](add_hardware_module.py)
Ajoute un bloc SystemVerilog dans `src/hw/`. CMake compile automatiquement ce fichier avec Verilator pour créer une bibliothèque C++ liée au projet.
```bash
./add_hardware_module.py --project-root /chemin/vers/projet --name FilterBlock --id filter_v1
```

### 5.5 [add_uart_hw_module.py](add_uart_hw_module.py)
Génère un bloc IP SystemVerilog encapsulé avec la logique UART pour synthèse sur FPGA.
```bash
./add_uart_hw_module.py --project-root /chemin/vers/projet --name UartFilter --id uart_filter_v1
```

### 5.6 [test.sh](test.sh)
Exécute la batterie de tests d'intégration (génération d'une matrice de 8 projets, validation des manifestes, compilation CMake, exécution des exécutables et vérification de l'idempotence).

---

## 6. Codes de Retour Standardisés des Scripts `add_*.py`
- `0` : Modification appliquée avec succès.
- `2` : Idempotent no-op (le module/id existe déjà avec la même définition).
- `1` : Erreur (ex: échec de validation, conflit de nom sans `--force`, fichier manquant).
