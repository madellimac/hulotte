# Instructions Copilot - Framework Hulotte

## Vue d'ensemble
Hulotte est un framework modulaire (C++17, SystemVerilog, Python) pour le prototypage, le test et la co-simulation matérielle/logicielle de chaînes de traitement d'embedded systems.

Technologies clés :
- **StreamPU** : Moteur d'exécution dataflow basé sur des tâches (`tsk`) et des sockets (`sck`).
- **AFF3CT** : Bibliothèque de codage de canal (Reed-Solomon, Polar, LDPC, etc.).
- **Verilator** : Simulation C++ de modules SystemVerilog (co-simulation HW/SW).
- **Boost ASIO / UART** : Communication série pour cartes FPGA (Hardware-in-the-Loop).

## Arborescence du dépôt
- `create_project.py` : Script CLI pour générer un projet Hulotte.
- `add_custom_module.py` : Ajoute un module C++ StreamPU dans `src/custom/`.
- `add_hardware_module.py` : Ajoute un bloc SystemVerilog dans `src/hw/` (simulé via Verilator).
- `add_uart_hw_module.py` : Ajoute un bloc SystemVerilog enveloppé UART pour synthèse FPGA.
- `templates/` : Modèles Jinja2 (`CMakeLists.txt.j2`, `main.cpp.j2`, `hw_module.sv.j2`, `VerilatorSimulation.hpp.j2`, etc.).
- `Common/streampu/` : Composants partagés C++ (`sw/` : `Comparator`, `UartFrameIO`) et SystemVerilog (`hw/` : `uart_recv`, `UART_fifoed_send_V1`).
- `test.sh` : Matrix de tests d'intégration et de non-régression.

## Règles & Conventions de Code

### Modules C++ (StreamPU)
- Créés dans `src/custom/`, héritent de `spu::module::Module`.
- Les données transitent via des liaisons de sockets (`source["tsk::sck"] = destination["tsk::sck"]`).

### Blocs Matériels (SystemVerilog & Verilator)
- Placés dans `src/hw/`, instanciés côté C++ via `VerilatorSimulation<VModel_<BlockName>>`.
- Respectent la politique de contrôle de flux Ready/Valid :
  - `in_data` / `out_data` (bus de données)
  - `in_val` / `out_val` (validité)
  - `in_rdy` / `out_rdy` (prêt à recevoir)
- Fichiers se terminant par `Core.sv` : ce sont des sous-modules internes, exclus des top-levels Verilator.

### Manifeste de Projet (`hulotte.project.json`)
- Présent à la racine de tout projet Hulotte généré.
- Gère le statut des fonctionnalités (`streampu`, `aff3ct`, `custom`, `hardware`, `uart_io`), le mode du pipeline (`minimal`, `hw_only`, `uart_only`, `co_simulation`) et un journal d'opérations.

### Behavior & Codes de retour des scripts `add_*.py`
- Tous les scripts `add_*.py` doivent être **idempotents** (basés sur `--id` et comparaison de contenu) :
  - `0` : Modification appliquée avec succès.
  - `2` : Idempotent no-op (ressource déjà présente à l'identique).
  - `1` : Erreur (validation, conflit de nom sans `--force`, etc.).
