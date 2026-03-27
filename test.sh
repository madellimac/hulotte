#!/bin/bash

# Configuration des chemins (A adapter selon votre arborescence)
# On suppose par defaut que les dossiers projets sont au meme niveau que hulotte
STREAMPU_ROOT="./streampu"
AFF3CT_ROOT="./aff3ct"

# Dossier de sortie pour les tests
OUTPUT_DIR="test_projects"
rm -rf "$OUTPUT_DIR"

mkdir -p "$OUTPUT_DIR"

echo "=========================================="
echo "Creation de 8 projets de test dans $OUTPUT_DIR"
echo "=========================================="

# Boucle sur les 3 options binaires
for aff3ct in "no-aff3ct" "aff3ct"; do
    for custom in "no-custom" "custom"; do
        for hw in "no-hw" "hw"; do
            
            # Construction d'un nom explicite
            # Exemple: proj_aff3ct_custom_nohw
            
            NAME_PART=""
            
            if [ "$aff3ct" == "aff3ct" ]; then NAME_PART="${NAME_PART}_aff3ct"; fi
            if [ "$custom" == "custom" ]; then NAME_PART="${NAME_PART}_custom"; fi
            if [ "$hw" == "hw" ]; then NAME_PART="${NAME_PART}_hw"; fi
            
            # Si aucune option, on l'appelle 'minimal'
            if [ -z "$NAME_PART" ]; then NAME_PART="_minimal"; fi
            
            PROJ_NAME="test${NAME_PART}"
            
            echo " Génération du projet : $PROJ_NAME"
            echo " Options: --$aff3ct --$custom --$hw"
            
            # Execution du script python depuis le dossier parent
            # On passe les chemins des librairies pour éviter l'interactivité
            
            # Use venv if available
            PYTHON_CMD="python3"
            if [ -f ".venv/bin/python" ]; then
                PYTHON_CMD=".venv/bin/python"
            elif [ -f "../.venv/bin/python" ]; then
                PYTHON_CMD="../.venv/bin/python"
            fi
            
            $PYTHON_CMD create_project.py \
                --name "$PROJ_NAME" \
                --$aff3ct \
                --$custom \
                --$hw \
                --streampu-root "$STREAMPU_ROOT" \
                --aff3ct-root "$AFF3CT_ROOT" \
                > /dev/null
            
            # Deplacement dans le dossier de test
            if [ -d "$PROJ_NAME" ]; then
                mv "$PROJ_NAME" "$OUTPUT_DIR/"
                echo " [OK] Projet créé."
            else
                echo " [ERREUR] Le projet $PROJ_NAME n'a pas été créé correctement."
                exit 1
            fi
            
        done
    done
done

echo "=========================================="
echo "=========================================="
echo "Terminé. 8 projets créés dans '$OUTPUT_DIR/'"

# ============================================================
# Build and run each project -- check exit codes for PASS/FAIL
# ============================================================

FAILED=0

run_test() {
    local name=$1
    echo ""
    echo "--- Testing: $name ---"
    cd "$OUTPUT_DIR/$name" || { echo "[FAIL BUILD] $name: directory not found"; FAILED=1; return; }

    if ! ./build.sh > build_log.txt 2>&1; then
        echo "[FAIL BUILD] $name: build failed (see $OUTPUT_DIR/$name/build_log.txt)"
        FAILED=1
        cd - > /dev/null
        return
    fi
    echo "  Build OK"

    if (cd build && ./"$name" > run_log.txt 2>&1); then
        echo "  [PASS] $name"
    else
        echo "  [FAIL RUN] $name (see $OUTPUT_DIR/$name/build/run_log.txt)"
        FAILED=1
    fi

    cd - > /dev/null
}

run_test test_minimal
run_test test_hw
run_test test_custom
run_test test_custom_hw
run_test test_aff3ct
run_test test_aff3ct_hw
run_test test_aff3ct_custom
run_test test_aff3ct_custom_hw

echo ""
echo "=========================================="
if [ "$FAILED" -eq 0 ]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED -- see logs above"
fi
echo "=========================================="
exit $FAILED
