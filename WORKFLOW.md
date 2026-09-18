

Le workflow graph moderne est la nouvelle chaîne de génération déclarative de Hulotte. Au lieu d’écrire directement tout le `main.cpp`, on décrit un graphe de modules dans des fichiers YAML, puis Hulotte génère le code C++ correspondant.

**Vue d’ensemble**

```text
pipeline.yaml
      +
catalog/modules.yaml
      |
      v
chargement YAML
      |
      v
validation du graphe
      |
      v
résolution des modules du catalogue
      |
      v
génération de generated/main.cpp
      |
      v
génération de generated/CMakeLists.txt
      |
      v
CMake + compilation
```

Le point d’entrée est `hulotte.py`, avec trois commandes :

```bash
hulotte.py init ...
hulotte.py generate ...
hulotte.py build ...
```

## 1. `init` : créer un projet externe

Commande typique :

```bash
python framework/hulotte.py init "$HOME/projects/my_pipeline" \
    --hulotte-root /home/cleroux/PROJECTS/hulotte \
    --streampu-root /path/to/streampu
```

`init` crée un projet indépendant du dépôt Hulotte, via `init_project()` dans `project.py`.

Il crée notamment :

```text
my_pipeline/
├── hulotte.project.yaml
├── pipeline.yaml
├── src/
│   └── custom/
├── hardware/
│   └── sv/
├── generated/
└── .gitignore
```

Le fichier `hulotte.project.yaml` contient :

- le nom du projet ;
- le chemin vers Hulotte ;
- le chemin vers StreamPU ;
- éventuellement le chemin vers AFF3CT ;
- les capacités disponibles.

Le projet ne copie pas les templates ni le code interne de Hulotte. Il référence l’installation Hulotte comme outil externe.

## 2. `pipeline.yaml` : décrire le graphe

Le pipeline décrit les modules et leurs connexions.

Exemple de `pipeline.yaml` :

```yaml
modules:
  source:
    type: streampu
    catalog: source_random_int
    parameters:
      frame_size: 16
    sockets:
      generate:
        outputs:
          out_data: {type: int32, frame_size: 16}

  filter:
    type: custom
    catalog: custom_passthrough
    parameters:
      frame_size: 16
    sockets:
      process:
        inputs:
          in: {type: int32, frame_size: 16}
        outputs:
          out: {type: int32, frame_size: 16}

connections:
  - from: source.generate.out_data
    to: filter.process.in
```

Le pipeline contient :

- des **modules**, qui deviennent des objets C++ ;
- des **paramètres**, utilisés par les constructeurs ;
- des **sockets**, utilisés pour vérifier les connexions ;
- des **connexions**, exprimées sous la forme `module.tâche.socket` ;
- éventuellement des **ressources partagées**.

Le graphe représente donc la structure logique du pipeline, tandis que le catalogue contient les informations nécessaires pour produire le C++.

## 3. `catalog/modules.yaml` : décrire comment générer chaque module

Le catalogue, chargé par `catalog.py`, associe un identifiant logique à une classe C++.

Extrait :

```yaml
source_random_int:
  type: streampu
  class: spu::module::Source_random<int>
  include: streampu.hpp
  constructor:
    - parameter: frame_size
  sockets:
    generate:
      outputs:
        out_data: {type: int32}
```

Cela signifie :

- `source_random_int` correspond à `spu::module::Source_random<int>` ;
- il faut inclure `streampu.hpp` ;
- son constructeur reçoit `frame_size` ;
- sa tâche `generate` possède une sortie `out_data`.

Pour le module custom :

```yaml
custom_passthrough:
  type: custom
  class: CustomModule
  include: custom/CustomModule.hpp
  constructor:
    - parameter: frame_size
```

Le pipeline choisit donc le module par :

```yaml
catalog: custom_passthrough
```

Le catalogue décrit aussi les sockets C++ spécifiques à AFF3CT. Par exemple, certains modules AFF3CT ne peuvent pas être connectés avec la simple notation :

```cpp
module["task::socket"]
```

Le catalogue peut fournir :

```yaml
cpp_task: enc::tsk::encode
cpp_socket: (int)enc::sck::encode::X_N
```

afin de générer la syntaxe exacte attendue par AFF3CT.

## 4. `generate` : parser, valider et générer le C++

Commande :

```bash
python framework/hulotte.py generate \
    --project-root tests/unit/fixtures/minimal_project
```

La fonction `generate_project()` dans `project.py` effectue les étapes suivantes :

1. vérifie que le répertoire du projet existe ;
2. charge `hulotte.project.yaml` si présent ;
3. recherche `pipeline.yaml` ;
4. recherche le catalogue :
   - d’abord dans `project_root/catalog/modules.yaml` ;
   - sinon dans l’installation Hulotte ;
5. charge le pipeline ;
6. charge le catalogue ;
7. valide le graphe ;
8. génère `generated/main.cpp`.

Le chemin de sortie par défaut est :

```text
generated/main.cpp
```

On peut le modifier avec :

```bash
--output autre/fichier.cpp
```

## 5. Validation du graphe

La validation est réalisée par `validation.py`.

Elle contrôle notamment :

- qu’il existe au moins un module ;
- que les types de modules sont connus ;
- que les points de connexion ont le format :

```text
module.task.socket
```

- que les modules ciblés existent ;
- que les sockets existent ;
- qu’une entrée n’est pas connectée plusieurs fois ;
- que les types des sockets sont compatibles ;
- que les tailles de trames sont compatibles.

Exemple rejeté par `pipeline.invalid.yaml` :

```yaml
source: int32
filter: uint8
```

La connexion est refusée car `int32` et `uint8` sont incompatibles.

Le modèle `pipeline.py` calcule également un ordre topologique. Cela permet de générer les modules dans un ordre cohérent avec leurs dépendances et de détecter les cycles.

## 6. Génération du `main.cpp`

La génération est effectuée par `generator.py`.

Pour le pipeline minimal, le résultat ressemble conceptuellement à :

```cpp
#include <streampu.hpp>
#include "custom/CustomModule.hpp"

using namespace spu;
using namespace spu::module;

int main()
{
    Source_random<int> source(16);
    CustomModule filter(16);

    std::vector<runtime::Task*> first_tasks;
    first_tasks.push_back(&source("generate"));

    runtime::Sequence sequence(first_tasks);

    source["generate::out_data"] = filter["process::in"];

    sequence.exec_seq();
    return 0;
}
```

Le générateur :

- inclut les headers déclarés dans le catalogue ;
- instancie les ressources partagées ;
- instancie les modules dans l’ordre topologique ;
- identifie les modules sources ;
- crée la séquence StreamPU ;
- génère les liaisons entre sockets ;
- exécute une frame avec `sequence.exec_seq()`.

Le fichier commence par :

```cpp
// Generated by Hulotte. Do not edit.
```

Il s’agit donc d’un artefact généré, pas d’un fichier à modifier manuellement.

## 7. Gestion des ressources partagées

Les pipelines peuvent déclarer des ressources communes.

Dans `pipeline.yaml` :

```yaml
resources:
  polynomial:
    type: rs_polynomial_generator
    parameters:
      N_rs: 7
      t: 1
```

L’encodeur et le décodeur utilisent tous deux cette ressource :

```yaml
constructor:
  - parameter: K_rs
  - parameter: N_rs
  - resource: polynomial
```

Le générateur produit alors une seule instance :

```cpp
RS_polynomial_generator polynomial(7, 1);
Encoder_RS<int> encoder(5, 7, polynomial);
Decoder_RS_std<int, float> decoder(5, 7, polynomial);
```

C’est une différence importante par rapport à une génération naïve où chaque module créerait sa propre ressource.

## 8. `build` : générer puis compiler

Commande :

```bash
python framework/hulotte.py build \
    --project-root tests/unit/fixtures/minimal_project \
    --streampu-root /path/to/streampu
```

`build_project()` :

1. appelle automatiquement `generate_project()` ;
2. vérifie la présence de StreamPU ;
3. détecte si le pipeline utilise AFF3CT ;
4. écrit un `generated/CMakeLists.txt` ;
5. lance CMake ;
6. compile le projet ;
7. retourne le chemin vers l’exécutable.

La structure obtenue est généralement :

```text
project/
├── pipeline.yaml
├── src/custom/
└── generated/
    ├── main.cpp
    ├── CMakeLists.txt
    └── build/
        └── project
```

Pour un pipeline StreamPU seul, CMake :

- inclut `src/custom/*.cpp` automatiquement ;
- ajoute les headers StreamPU ;
- lie `libstreampu.a` ;
- lie `cpptrace` et `Threads`.

Pour un pipeline AFF3CT, il utilise les headers et bibliothèques AFF3CT, avec les headers StreamPU embarqués par AFF3CT.

## 9. Différence avec l’ancien workflow

L’ancien workflow repose sur :

```bash
create_project.py
add_custom_module.py
add_hardware_module.py
build.sh
```

Il génère directement un projet CMake complet, un `main.cpp` basé sur des templates Jinja et un manifeste `hulotte.project.json`.

Le workflow graph moderne repose sur :

```bash
hulotte.py init
hulotte.py generate
hulotte.py build
```

Il utilise :

- `pipeline.yaml` pour le graphe ;
- `catalog/modules.yaml` pour les métadonnées de génération ;
- `hulotte.project.yaml` pour les dépendances et capacités ;
- `generated/` pour les artefacts.

En résumé :

```text
Ancien workflow :
options CLI -> templates CMake/main.cpp -> projet généré

Workflow graph :
pipeline YAML + catalogue YAML -> C++ généré -> CMake -> exécutable
```

## Limites actuelles

Le workflow graph est encore une première tranche fonctionnelle :

- il couvre principalement StreamPU et le scénario AFF3CT Reed-Solomon ;
- `build` est décrit comme software-only dans `project.py` ;
- Verilator et UART ne sont pas encore intégrés au générateur graph ;
- les modules custom sont pris en compte surtout via `src/custom/*.cpp` et le catalogue ;
- la validation actuelle vérifie la cohérence déclarative du graphe, mais ne remplace pas une compilation ;
- la GUI utilise encore principalement le workflow legacy et les manifestes JSON.

La matrice `test.sh` teste donc surtout l’ancien workflow. Le workflow graph moderne est principalement couvert par les tests unitaires Python et les tests conditionnels de compilation dans `test_project_generation.py` et `test_aff3ct_catalog.py`.