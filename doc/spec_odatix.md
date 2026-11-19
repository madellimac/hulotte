# Spec : intégration d'Odatix dans hulotte

État : **validée dans ses grandes lignes par Camille** (2026-11-19), puis mise à jour après un premier essai réel
d'Odatix 4.0.0 avec Vivado 2023.1 sur d7010‑cl (2026-11-19, voir « Essai réel »). **Phase 1 implémentée**
(`synth add`, 2026-11-19) ; phases 1 bis, 1 ter et 2 à faire.

## Décisions

- [x] D1. **Hulotte lance Odatix** (`hulotte synth run`). Un concepteur qui synthétise fait tourner hulotte sur une machine qui a les outils de synthèse : hulotte, Odatix et l'outil sont sur la même machine.
- [x] D2. Outil et cible par défaut : Vivado, `xc7a100t-csg324-1` (Nexys A7).
- [x] D3. Enveloppe registrée des entrées‑sorties (`--wrap-io`) activée par défaut.
- [x] D4. Témoin de vérification : **l'empreinte est écrite par le test lui‑même** (`check_hw`) quand il passe, grâce à une méthode de l'adaptateur Verilator. `synth run` refuse de synthétiser un RTL modifié depuis la vérification, sauf avec `--force`. Pas de commande `synth verify`.
- [x] D5. Pour le concours, le classement combinera cycles et Fmax ou surface : la phase 2 (rapport) est prioritaire.
- [x] D6. `synth run --synth-only` arrête Odatix après la synthèse (`--until synthesis`), sans placement-routage (Camille, 2026-11-19).
- [x] D7. Le rapport affiche une Fmax estimée depuis une synthèse à fréquence fixe, marquée « estimée », quand `fmax` n'a pas été lancé (Camille, 2026-11-19).
- [x] D8. Version minimale d'Odatix : 4.0.0 (Camille, 2026-11-19).

## Objectif

Depuis un projet hulotte, synthétiser avec Odatix un bloc `src/hw/<Bloc>.sv` **dans la configuration qui a été vérifiée** par la simulation Verilator. Ensuite, combiner les cycles mesurés par Verilator avec la Fmax et les ressources mesurées par Odatix.

## Principes

- Aucun code d'Odatix n'est copié dans hulotte, qui écrit des fichiers de configuration et appelle la commande `odatix`. Odatix (GPL‑3.0) reste une dépendance optionnelle (`pip install odatix`, version 4.0.0 au minimum, D8) ; `hulotte doctor` vérifie sa présence et sa version.
- La vérification peut se faire sur une machine (le Mac) et la synthèse sur une autre (un serveur avec Vivado) : l'empreinte est un fichier commité avec le projet. On vérifie, on commite, puis sur le serveur `git pull` et `synth run`.
- Tout ce qui manque se corrige dans hulotte. `istc_challenge_2027` sert de premier exemple.

## Flux d'utilisation

```sh
hulotte synth add    istc_challenge_2027 --name Hamming_decoder_hw   # une fois
build/istc_challenge_2027 check_hw                                   # [PASS] : écrit l'empreinte
hulotte synth run    istc_challenge_2027 --name Hamming_decoder_hw --fmax
hulotte synth report istc_challenge_2027                             # phase 2
```

## Phase 1 : générer l'espace Odatix (`synth add`)

### Commande

```sh
hulotte synth add <projet> --name Hamming_decoder_hw \
        [--tool vivado] [--target xc7a100t-csg324-1] [--wrap-io | --no-wrap-io]
```

- Valeurs par défaut : celles de D2 et D3.
- La commande refuse de continuer si `src/hw/<Bloc>.sv` n'existe pas.
- Elle affiche un aperçu, comme `module add`, et ne réécrit pas un fichier existant sans `--force`.

### Fichiers créés dans le projet

```
synth/
  odatix.yml                                  chemins par défaut, default_tool: vivado
  synth_settings.yml                          architectures: [Hamming_decoder_hw/verified]
  fmax_settings.yml                           architectures: [Hamming_decoder_hw/verified]
  odatix_userconfig/
    architectures/Hamming_decoder_hw/
      _settings.yml
      verified.txt                            configuration vérifiée
    targets/target_vivado.yml                 constraint_file: constraints.xdc, targets: [xc7a100t-csg324-1]
  .gitignore                                  work/, results/
src/hw/synth/Hamming_decoder_hw_synth_top.sv  enveloppe registrée (D3)
```

### `_settings.yml`

Champs tirés de la documentation de référence d'Odatix (architecture settings) :

```yaml
rtl_path: "../src/hw"
top_level_file: "synth/Hamming_decoder_hw_synth_top.sv"   # ou Hamming_decoder_hw.sv avec --no-wrap-io
top_level_module: "Hamming_decoder_hw_synth_top"
clock_signal: "clk"
reset_signal: "reset"
use_parameters: Yes
start_delimiter: "module Hamming_decoder_hw_synth_top #("
stop_delimiter: ") ("
param_target_file: "synth/Hamming_decoder_hw_synth_top.sv"
fixed_freq_synthesis:
  list: [100]                  # fréquences par défaut de synth run, en MHz
fmax_synthesis:
  lower_bound: 50              # bornes de la recherche de Fmax, en MHz
  upper_bound: 500
```

Toutes ces clés sont lues par Odatix 4.0.0 (vérifié dans son code). `reset_active_low` n'est lu que par la
simulation d'Odatix : hulotte ne l'écrit pas. Odatix copie tout le dossier `rtl_path` dans son dossier de
travail avant d'y remplacer les paramètres : `src/hw` reste intact.

Le délimiteur de début est l'en‑tête complet `module <Top> #(`, et non `#(` seul : l'enveloppe instancie le bloc avec `#(`, qui apparaîtrait deux fois. `synth add` vérifie que l'en‑tête apparaît une seule fois, dans le bloc et dans l'enveloppe générée ; un test le vérifie avec `odatix replace`, la commande de remplacement d'Odatix. Un premier essai a montré le piège : un commentaire qui cite l'en‑tête suffit à faire remplacer au mauvais endroit.

### `verified.txt`

C'est le texte exact qu'Odatix insère entre les délimiteurs : les paramètres d'interface du bloc, tels que l'adaptateur C++ les utilise.

```
    parameter int IN_WIDTH  = 6,
    parameter int IN_LANES  = 7,
    parameter int OUT_WIDTH = 1,
    parameter int OUT_LANES = 4
```

Hulotte lit ces valeurs dans l'adaptateur généré `src/custom/<Bloc>.hpp`, qui en est la source de vérité.

### Entrées‑sorties : enveloppe registrée (`--wrap-io`)

La documentation d'Odatix ne dit rien d'une synthèse *out of context*, ni des registres d'entrée‑sortie : les ports du top restent ceux du RTL. Or un bloc nu a deux défauts :

- sur FPGA, les chemins vers les broches faussent la Fmax ;
- un bloc à larges ports (LANES × WIDTH) dépasse vite le nombre de broches. Le CSG324 en a 210, alors que l'exemple Hamming en utilise une cinquantaine.

Hulotte génère donc `src/hw/synth/<Bloc>_synth_top.sv`, qui :

- place un registre sur chaque entrée et chaque sortie, ce qui garde la mesure de Fmax de registre à registre, celle du cœur ;
- reprend les mêmes paramètres et le même en‑tête `#( … ) (`, pour que le remplacement d'Odatix fonctionne.

Dans un premier temps, le nombre de broches n'est pas réduit (pas de sérialisation des ports) : c'est un point à revoir pour les gros blocs.

Ce fichier ne sert qu'à la synthèse. Il est dans un sous‑dossier, `src/hw/synth/`, que le glob CMake de `src/hw` (non récursif) ne voit pas : Verilator ne le compile pas, et les projets existants n'ont pas à changer leur CMake. Odatix, lui, copie `rtl_path` avec ses sous‑dossiers et Vivado lit les `.sv` récursivement (vérifié dans le code d'Odatix 4.0.0).

L'enveloppe enregistre aussi `in_ready` et `out_ready` : c'est un banc de mesure, pas une enveloppe fonctionnelle du flux.

## Phase 1 bis : témoin de vérification (D4)

### Écriture par le test

- **CMake** (template du projet) : une règle génère, pour chaque bloc, un en‑tête `<Bloc>_rtl_hash.hpp` contenant l'empreinte SHA‑256 de `src/hw/<Bloc>.sv` (`cmake -E sha256sum`). La règle dépend du `.sv` : l'empreinte est donc toujours celle du RTL **compilé dans le simulateur**. CMake passe aussi au code le chemin du projet (`HULOTTE_PROJECT_DIR`).
- **Adaptateur Verilator** (template) : nouvelle méthode
  ```cpp
  void mark_verified(const std::string& test_name) const;
  ```
  qui écrit `synth/verified/<Bloc>.yml` :
  ```yaml
  module: Hamming_decoder_hw
  rtl: src/hw/Hamming_decoder_hw.sv
  rtl_sha256: 3f5a...
  parameters: { IN_WIDTH: 6, IN_LANES: 7, OUT_WIDTH: 1, OUT_LANES: 4 }
  test: check_hw
  date: 2026-11-19T15:42:00
  cycles: { latency_min: 17, latency_max: 17, interval_min: 18, interval_max: 18 }
  ```
- **Le test** (code de l'utilisateur) l'appelle seulement quand il passe :
  ```cpp
  if (total_differences == 0)
      decoder_hw.mark_verified("check_hw");
  ```

Les cycles sont écrits dans le même fichier : la phase 2 n'a pas besoin d'une méthode à part.

### Contrôle

- `hulotte synth status <projet>` recalcule l'empreinte de chaque `src/hw/<Bloc>.sv` et la compare au fichier témoin : **vérifié**, **modifié depuis la vérification** ou **jamais vérifié**. Il compare aussi les paramètres à `verified.txt`.
- `hulotte synth run` fait le même contrôle et refuse de lancer Odatix si le bloc n'est pas vérifié, sauf avec `--force` (le rapport signale alors « non vérifié »).

Le témoin est déclaratif : il prouve que ce RTL, avec ces paramètres, a passé le test qui a appelé `mark_verified`, rien de plus.

## Phase 1 ter : lancer Odatix (`synth run`, D1)

```sh
hulotte synth run <projet> --name Hamming_decoder_hw \
        [--fmax | --freq 100 [--freq 200 ...]] [--synth-only] [--target ...] [-j N] [--force]
```

- Contrôle du témoin (ci‑dessus), puis contrôle d'Odatix (`odatix` dans le PATH, version minimale).
- Lance, dans `synth/`, la commande Odatix correspondante (options confirmées sur Odatix 4.0.0) :
  ```sh
  odatix fmax  -c odatix.yml -i fmax_settings.yml  -a Hamming_decoder_hw/verified -t vivado --target xc7a100t-csg324-1 -y -E -Q -j N
  odatix synth -c odatix.yml -i synth_settings.yml -a Hamming_decoder_hw/verified -t vivado --target xc7a100t-csg324-1 -y -E -Q -j N --at 100
  ```
  La commande exacte est affichée avant le lancement, pour pouvoir la relancer à la main.
- `-y` évite la question de confirmation, `-E` fait attendre Odatix jusqu'à la fin des jobs puis rendre la main
  avec un code de sortie. Sans terminal, Odatix signale qu'il ne peut pas afficher son moniteur et attend (essai
  du 2026-11-19, code de sortie 0).
- Odatix confie les jobs à une **session** (un démon) : Ctrl‑C arrête l'attente, **pas les jobs**, qui continuent.
  hulotte le dit avant le lancement et renvoie à `odatix ps` et `odatix stop` sans les refaire.
- Par défaut, le flow `standard` de Vivado enchaîne `elaboration`, `synthesis` et `pnr` (placement et routage).
  L'option `--synth-only` de hulotte passe `--until synthesis` à Odatix (D6).
- Ordre de grandeur : environ 4 minutes pour un compteur 8 bits à une fréquence, dont l'essentiel est le
  démarrage de Vivado. Une recherche de Fmax en lance plusieurs.

## Phase 2 : rapport cycles et Fmax (prioritaire, D5)

- `hulotte synth report <projet>` lit les fichiers témoins (cycles) et les résultats d'Odatix, puis affiche par bloc et par cible :

  | Bloc | Cible | Vérifié | Fmax (MHz) | LUT | Reg | Latence (cycles / ns) | Intervalle | Débit (Mmots/s) |
  |---|---|---|---|---|---|---|---|---|

  avec débit = Fmax ÷ intervalle, et latence en ns = cycles ÷ Fmax.
- Le même rapport en YAML (`synth/report.yml`), pour le classement du concours.

### Où lire les résultats d'Odatix (essai réel)

- Un seul fichier par outil : `synth/results/results_vivado.yml` (`schema: 2`), complété à chaque run.
- Une entrée par job **et par étape** du flow. `meta` identifie l'entrée : `type` (`custom_freq_synthesis`
  pour `synth`), `target`, `architecture`, `configuration`, `tool`, `flow`, `frequency`, `step`
  (`elaboration`, `synthesis`, `pnr`), `_last_step`, `timestamp`.
- `metrics` : `LUT_count`, `LUT_percent`, `Reg_count`, `Reg_percent`, `BRAM_count`, `DSP_count`,
  `Worst_Slack` (ns), `Static_Power`, `Dynamic_Power`, `Total_Power` (W), et après élaboration le nombre
  d'éléments RTL (`RTL_Reg_count`, `RTL_Arith_count`…). Les unités sont dans `units`.
- hulotte prend l'entrée de la dernière étape faite (`_last_step`, ou à défaut `pnr`, puis `synthesis`). Il
  n'analyse pas les rapports bruts de Vivado, qui restent dans
  `synth/work/custom_freq_synthesis/vivado/<cible>/<Bloc>/<config>/<f>MHz/report/`.
- Mesures de l'essai (compteur 8 bits, 100 MHz, `xc7a100t-csg324-1`) : après `pnr`, 9 LUT, 8 registres,
  `Worst_Slack` 7,792 ns, 0,094 W.
- **Sans `odatix fmax`**, une Fmax estimée se déduit d'une synthèse à fréquence fixe :
  Fmax ≈ 1000 / (1000 / f − Worst_Slack) MHz, soit environ 450 MHz pour l'essai. Le rapport l'affiche en
  la marquant « estimée » (D7) ; une Fmax mesurée par `odatix fmax` la remplace quand elle existe.
- **À confirmer** : le `type` et les champs des entrées écrites par `odatix fmax` (pas encore essayé, à la
  demande de Camille).

## Phase 3 : exploration de paramètres (plus tard, à discuter)

- Les paramètres d'interface (WIDTH, LANES) restent fixes : les changer invalide l'adaptateur et la vérification.
- Les paramètres internes du bloc (parallélisme, pipeline) pourront être explorés avec les `configurations` et `variables` d'Odatix, ou avec `odatix dse`.
- Chaque configuration explorée devrait idéalement repasser par la vérification, ce qui impose que les paramètres internes soient visibles aussi de Verilator. C'est à concevoir.

## Ce qui change dans hulotte

- `hulotte.py` : sous‑commande `synth` avec `add`, `status`, `run` et `report` ; contrôle d'Odatix dans `doctor`.
- `templates/synth/` : `_settings.yml.j2`, `verified.txt.j2`, `target_vivado.yml.j2`, `synth_settings.yml.j2`, `fmax_settings.yml.j2`, `odatix.yml.j2`, `synth_top.sv.j2`, `preview.txt.j2`.
- `templates/verilator/` : méthode `mark_verified` de l'adaptateur.
- `templates/project/CMakeLists.txt.j2` : génération de `<Bloc>_rtl_hash.hpp` et définition de `HULOTTE_PROJECT_DIR` (phase 1 bis). L'enveloppe n'a pas besoin d'y être exclue (`src/hw/synth/`).
- `requirements.txt` : Odatix en dépendance optionnelle, version minimale.
- `tests/` :
  - génération des fichiers, valeurs lues dans l'adaptateur, unicité des délimiteurs ;
  - compilation de l'enveloppe par Verilator en `--lint-only` (rapide, ce n'est pas une synthèse) ;
  - `mark_verified` dans un projet de test, puis `status` avant et après modification du `.sv` ;
  - `run` avec un **faux exécutable `odatix`** placé en tête du PATH, qui enregistre ses arguments et écrit des résultats factices ; refus sans témoin, passage avec `--force` ;
  - `report` sur ces résultats factices ;
  - **aucun test ne lance Odatix ni une synthèse**.
- `README.md` (section « Synthesis with Odatix ») et `CHANGELOG.md`.
- `istc_challenge_2027` : `hulotte synth add` sur `Hamming_decoder_hw`, appel de `mark_verified` dans `check_hw`. `synth/` (y compris `verified/`) est commité, `work/` et `results/` sont ignorés.

## Hors périmètre

Lancer Odatix à distance (ssh), la synthèse ASIC, Yosys avec nextpnr (pas d'exemple de cible dans la documentation), la réduction du nombre de broches, la phase 3.

## Points ouverts

1. Format des résultats de `odatix fmax` : `odatix synth` est réglé (voir phase 2), `fmax` n'a pas été essayé.
2. Le placement-routage est fait par défaut, avec de vraies broches : un bloc dont l'enveloppe dépasse les 210
   broches du CSG324 échouera au `pnr`. L'exemple Hamming en utilise une cinquantaine. Pour les gros blocs :
   `--synth-only` (D6), ou réduction des broches (hors périmètre pour l'instant).

Réglés par l'essai du 2026-11-19 : nom et format des résultats de `synth`, synthèse et placement-routage,
présence de Vivado 2023.1 et d'Odatix 4.0.0 sur d7010‑cl, options de la ligne de commande. Réglés par Camille
le même jour : `--synth-only` (D6), Fmax estimée (D7), version minimale (D8).

## Essai réel (2026-11-19, d7010‑cl)

Odatix 4.0.0 dans le venv de hulotte, Vivado 2023.1. Espace créé par `odatix init -y --examples`, puis
`odatix synth -t vivado -a Example_Counter_sv/08bits --at 100 -y -E -j 1 -Q` : un job réussi en 3 min 44 s,
flow `standard` complet (élaboration, synthèse, placement et routage).

## Références (documentation d'Odatix lue le 2026-11-19)

- Architecture settings : <https://odatix.readthedocs.io/en/latest/docs/reference/architecture/>
- Targets : <https://odatix.readthedocs.io/en/latest/docs/reference/targets/>
- Run settings : <https://odatix.readthedocs.io/en/latest/docs/reference/run_settings/>
- Commandes : <https://odatix.readthedocs.io/en/latest/docs/commands/>
- Métriques : <https://odatix.readthedocs.io/en/latest/docs/results/metrics/>
- Dépôt : <https://github.com/jsaussereau/Odatix>
