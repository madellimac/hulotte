# Résumé du workflow Hulotte

Hulotte propose un workflow graph déclaratif qui permet de décrire un pipeline dans des fichiers YAML, puis de générer automatiquement le code C++ et les fichiers CMake nécessaires à sa compilation.

Le pipeline est défini dans `pipeline.yaml`. Il décrit les modules, leurs paramètres, leurs sockets, leurs connexions et éventuellement les ressources partagées.

Le fichier `catalog/modules.yaml` associe chaque identifiant de module à une classe C++, ses headers, son constructeur et ses sockets. Il permet aussi de définir les syntaxes spécifiques nécessaires aux modules AFF3CT.

Les principales commandes sont :

- `hulotte.py init` : crée un projet externe indépendant du dépôt Hulotte ;
- `hulotte.py generate` : charge, valide et transforme le pipeline en `generated/main.cpp` ;
- `hulotte.py build` : génère le code, crée `generated/CMakeLists.txt`, puis compile le projet avec CMake.

La validation vérifie notamment l’existence des modules et sockets, le format des connexions, l’absence de connexions d’entrée multiples, la compatibilité des types et des tailles de trames. Un ordre topologique est également calculé pour détecter les cycles et instancier les modules dans le bon ordre.

Le générateur produit un `main.cpp` qui inclut les headers nécessaires, instancie les ressources partagées et les modules, crée une séquence StreamPU, connecte les sockets et exécute le pipeline.

Les ressources partagées sont déclarées une seule fois dans le pipeline, puis transmises aux constructeurs des modules concernés afin d’éviter les instances dupliquées.

Le workflow moderne remplace l’ancien système basé sur `create_project.py`, `add_custom_module.py`, `add_hardware_module.py`, `build.sh`, les templates Jinja et `hulotte.project.json`. Il utilise à la place `pipeline.yaml`, `catalog/modules.yaml`, `hulotte.project.yaml` et le répertoire `generated/`.

Les fichiers placés dans `generated/` sont des artefacts générés et ne doivent pas être modifiés manuellement.