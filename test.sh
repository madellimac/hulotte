#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration des chemins (A adapter selon votre arborescence)
# On suppose par defaut que les dossiers projets sont au meme niveau que hulotte
STREAMPU_ROOT="$SCRIPT_DIR/streampu"
AFF3CT_ROOT="$SCRIPT_DIR/aff3ct"

# Dossier de sortie pour les tests
OUTPUT_DIR="test_projects"
rm -rf "$OUTPUT_DIR"

mkdir -p "$OUTPUT_DIR"

# Enable CMake parallel builds
export CMAKE_BUILD_PARALLEL_LEVEL=$(nproc || echo 4)

# Use venv if available
PYTHON_CMD="python3"
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$(dirname "$SCRIPT_DIR")/.venv/bin/python" ]; then
    PYTHON_CMD="$(dirname "$SCRIPT_DIR")/.venv/bin/python"
fi

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
            
            $PYTHON_CMD "$SCRIPT_DIR/create_project.py" \
                --name "$PROJ_NAME" \
                --output-dir "$OUTPUT_DIR" \
                --$aff3ct \
                --$custom \
                --$hw \
                --streampu-root "$STREAMPU_ROOT" \
                --aff3ct-root "$AFF3CT_ROOT" \
                > /dev/null
            
            # Check project created at the expected location
            if [ -d "$OUTPUT_DIR/$PROJ_NAME" ]; then
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

    if ! "$PYTHON_CMD" "$SCRIPT_DIR/create_project.py" --validate-manifest ./hulotte.project.json > manifest_log.txt 2>&1; then
        echo "  [FAIL MANIFEST] $name: invalid manifest (see $OUTPUT_DIR/$name/manifest_log.txt)"
        FAILED=1
        cd - > /dev/null
        return
    fi
    echo "  Manifest OK"

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

run_add_scripts_idempotence_checks() {
    local id_proj="idempotence_case"
    local proj_dir="$OUTPUT_DIR/$id_proj"

    echo ""
    echo "--- Testing add_* idempotence ---"

    rm -rf "$proj_dir"

    if ! $PYTHON_CMD "$SCRIPT_DIR/create_project.py" \
        --name "$id_proj" \
        --output-dir "$OUTPUT_DIR" \
        --no-aff3ct \
        --no-custom \
        --hw \
        --no-uart-io \
        --streampu-root "$STREAMPU_ROOT" \
        --aff3ct-root "$AFF3CT_ROOT" > /dev/null; then
        echo "  [FAIL SETUP] could not generate $id_proj"
        FAILED=1
        return
    fi

    # 1) add_hardware_module.py: first run should modify, second should be no-op (exit 2)
    if ! "$SCRIPT_DIR/add_hardware_module.py" --project-root "$proj_dir" --name IdemBlock --id idem_hw_main > "$proj_dir/idem_hw_run1.log" 2>&1; then
        echo "  [FAIL IDEM] add_hardware first run failed (see $proj_dir/idem_hw_run1.log)"
        FAILED=1
        return
    fi
    "$SCRIPT_DIR/add_hardware_module.py" --project-root "$proj_dir" --name IdemBlock --id idem_hw_main > "$proj_dir/idem_hw_run2.log" 2>&1
    local rc_hw=$?
    if [ "$rc_hw" -ne 2 ]; then
        echo "  [FAIL IDEM] add_hardware second run expected exit 2, got $rc_hw"
        FAILED=1
        return
    fi

    # 2) add_custom_module.py: first run should modify, second should be no-op (exit 2)
    if ! "$SCRIPT_DIR/add_custom_module.py" --project-root "$proj_dir" --name IdemCustom --id idem_custom_main > "$proj_dir/idem_custom_run1.log" 2>&1; then
        echo "  [FAIL IDEM] add_custom first run failed (see $proj_dir/idem_custom_run1.log)"
        FAILED=1
        return
    fi
    "$SCRIPT_DIR/add_custom_module.py" --project-root "$proj_dir" --name IdemCustom --id idem_custom_main > "$proj_dir/idem_custom_run2.log" 2>&1
    local rc_custom=$?
    if [ "$rc_custom" -ne 2 ]; then
        echo "  [FAIL IDEM] add_custom second run expected exit 2, got $rc_custom"
        FAILED=1
        return
    fi

    # 3) add_uart_hw_module.py: first run should modify, second should be no-op (exit 2)
    if ! "$SCRIPT_DIR/add_uart_hw_module.py" --project-root "$proj_dir" --name IdemUartHw --id idem_uart_hw_main > "$proj_dir/idem_uart_hw_run1.log" 2>&1; then
        echo "  [FAIL IDEM] add_uart_hw first run failed (see $proj_dir/idem_uart_hw_run1.log)"
        FAILED=1
        return
    fi
    "$SCRIPT_DIR/add_uart_hw_module.py" --project-root "$proj_dir" --name IdemUartHw --id idem_uart_hw_main > "$proj_dir/idem_uart_hw_run2.log" 2>&1
    local rc_uart_hw=$?
    if [ "$rc_uart_hw" -ne 2 ]; then
        echo "  [FAIL IDEM] add_uart_hw second run expected exit 2, got $rc_uart_hw"
        FAILED=1
        return
    fi

    # Validate manifest and build final composed project.
    if ! $PYTHON_CMD "$SCRIPT_DIR/create_project.py" --validate-manifest "$proj_dir/hulotte.project.json" > "$proj_dir/idem_manifest.log" 2>&1; then
        echo "  [FAIL IDEM] manifest validation failed (see $proj_dir/idem_manifest.log)"
        FAILED=1
        return
    fi

    if ! (cd "$proj_dir" && ./build.sh > idem_build.log 2>&1); then
        echo "  [FAIL IDEM] composed project build failed (see $proj_dir/idem_build.log)"
        FAILED=1
        return
    fi

    echo "  [PASS] add_* idempotence checks"
}

run_add_scripts_idempotence_checks

echo ""
echo "=========================================="
if [ "$FAILED" -eq 0 ]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED -- see logs above"
fi
echo "=========================================="
exit $FAILED
