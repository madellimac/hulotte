#!/bin/bash
set -e

# ==============================================================================
# Script d'installation automatique pour PQC et ses dépendances (GMP, MPFR, GF2X, NTL, FLINT)
# Compatible MacOS (ARM64/Intel) et Linux.
# ==============================================================================

# 1. Configuration des répertoires
# ------------------------------------------------------------------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
WORK_DIR="$SCRIPT_DIR/pqc_dependencies_build"
INSTALL_PREFIX="$WORK_DIR/install"
SOURCES_DIR="$WORK_DIR/sources"
PQC_SRC_DIR="$SCRIPT_DIR/pqc"
PQC_INSTALL_DIR="$SCRIPT_DIR/pqc_install"

mkdir -p "$INSTALL_PREFIX"
mkdir -p "$SOURCES_DIR"

echo "[INFO] Les dépendances seront installées dans : $INSTALL_PREFIX"

# 2. Configuration de l'environnement de compilation
# ------------------------------------------------------------------------------
CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
export PATH="$INSTALL_PREFIX/bin:$PATH"
export LD_LIBRARY_PATH="$INSTALL_PREFIX/lib:$LD_LIBRARY_PATH"
export C_INCLUDE_PATH="$INSTALL_PREFIX/include:$C_INCLUDE_PATH"
export CPLUS_INCLUDE_PATH="$INSTALL_PREFIX/include:$CPLUS_INCLUDE_PATH"
export PKG_CONFIG_PATH="$INSTALL_PREFIX/lib/pkgconfig:$PKG_CONFIG_PATH"

# Détection MacOS pour les flags spécifiques
IS_MACOS=0
if [[ "$(uname)" == "Darwin" ]]; then
    IS_MACOS=1
    echo "[INFO] Système MacOS détecté."
fi

# 3. Téléchargement et Installation des dépendances
# ------------------------------------------------------------------------------

# --- GMP ---
cd "$SOURCES_DIR"
if [ ! -d "gmp-6.3.0" ]; then
    echo "[INFO] Téléchargement de GMP 6.3.0..."
    curl -LO https://gmplib.org/download/gmp/gmp-6.3.0.tar.xz
    tar -xf gmp-6.3.0.tar.xz
fi
if [ ! -f "$INSTALL_PREFIX/lib/libgmp.a" ]; then
    echo "[INFO] Compilation de GMP..."
    cd gmp-6.3.0
    ./configure --prefix="$INSTALL_PREFIX" --enable-cxx
    make -j"$CORES"
    make install
    cd ..
else
    echo "[INFO] GMP déjà installé."
fi

# --- MPFR ---
cd "$SOURCES_DIR"
if [ ! -d "mpfr-4.2.1" ]; then
    echo "[INFO] Téléchargement de MPFR 4.2.1..."
    rm -f mpfr-4.2.1.tar.gz
    curl -LO https://ftp.gnu.org/gnu/mpfr/mpfr-4.2.1.tar.gz
    tar -xf mpfr-4.2.1.tar.gz
fi
if [ ! -f "$INSTALL_PREFIX/lib/libmpfr.a" ]; then
    echo "[INFO] Compilation de MPFR..."
    cd mpfr-4.2.1
    ./configure --prefix="$INSTALL_PREFIX" --with-gmp="$INSTALL_PREFIX"
    make -j"$CORES"
    make install
    cd ..
else
    echo "[INFO] MPFR déjà installé."
fi

# --- GF2X ---
cd "$SOURCES_DIR"
if [ ! -d "gf2x-1.3.0" ]; then
    echo "[INFO] Téléchargement de GF2X 1.3.0..."
    rm -f gf2x-1.3.0.tar.gz
    curl -LO https://mirrors.mit.edu/sage/spkg/upstream/gf2x/gf2x-1.3.0.tar.gz
    tar -xf gf2x-1.3.0.tar.gz
fi
if [ ! -f "$INSTALL_PREFIX/lib/libgf2x.a" ]; then
    echo "[INFO] Compilation de GF2X..."
    cd gf2x-1.3.0
    # Patch pour les compilateurs récents (Clang 16+ sur MacOS) qui interdisent les déclarations implicites
    GF2X_CFLAGS="-O3"
    if [ "$IS_MACOS" -eq 1 ]; then
        GF2X_CFLAGS="$GF2X_CFLAGS -Wno-error=implicit-function-declaration"
    fi
    # On force CC_FOR_BUILD pour éviter l'erreur sur le test de compilation
    ./configure --prefix="$INSTALL_PREFIX" CC_FOR_BUILD="gcc $GF2X_CFLAGS" CFLAGS="$GF2X_CFLAGS"
    make -j"$CORES"
    make install
    cd ..
else
    echo "[INFO] GF2X déjà installé."
fi

# --- NTL ---
cd "$SOURCES_DIR"
if [ ! -d "ntl-11.5.1" ]; then
    echo "[INFO] Téléchargement de NTL 11.5.1..."
    curl -LO https://libntl.org/ntl-11.5.1.tar.gz
    tar -xf ntl-11.5.1.tar.gz
fi
if [ ! -f "$INSTALL_PREFIX/lib/libntl.a" ]; then
    echo "[INFO] Compilation de NTL..."
    cd ntl-11.5.1/src
    # NTL a besoin de savoir où sont GMP et GF2X
    # On active explicitement GF2X avec NTL_GF2X_LIB=on
    ./configure PREFIX="$INSTALL_PREFIX" \
        GMP_PREFIX="$INSTALL_PREFIX" \
        NTL_GF2X_LIB=on \
        GF2X_PREFIX="$INSTALL_PREFIX"
    make -j"$CORES"
    make install
    cd ../..
else
    echo "[INFO] NTL déjà installé."
fi

# --- FLINT ---
cd "$SOURCES_DIR"
if [ ! -d "flint-3.4.0" ]; then
    echo "[INFO] Téléchargement de FLINT 3.4.0..."
    curl -LO https://flintlib.org/download/flint-3.4.0.tar.gz
    tar -xf flint-3.4.0.tar.gz
fi
if [ ! -f "$INSTALL_PREFIX/lib/libflint.a" ]; then
    echo "[INFO] Compilation de FLINT..."
    cd flint-3.4.0
    ./configure --prefix="$INSTALL_PREFIX" \
        --with-gmp="$INSTALL_PREFIX" \
        --with-mpfr="$INSTALL_PREFIX"
    make -j"$CORES"
    make install
    cd ..
else
    echo "[INFO] FLINT déjà installé."
fi


# 4. Patch et Compilation de PQC
# ------------------------------------------------------------------------------
if [ ! -d "$PQC_SRC_DIR" ]; then
    echo "[INFO] Le dossier $PQC_SRC_DIR n'existe pas. Tentative de clonage de 'aff3ct/pqc'..."
    git clone https://github.com/aff3ct/pqc.git "$PQC_SRC_DIR"
    if [ ! -d "$PQC_SRC_DIR" ]; then
        echo "[ERROR] Échec du clonage ou dossier introuvable."
        exit 1
    fi
fi

# Lien symbolique vers StreamPU si présent (évite l'erreur find_package(StreamPU))
if [ -d "$SCRIPT_DIR/streampu" ] && [ ! -d "$PQC_SRC_DIR/streampu" ]; then
    echo "[INFO] Création du lien symbolique vers 'streampu'..."
    ln -s "$SCRIPT_DIR/streampu" "$PQC_SRC_DIR/streampu"
fi

echo "[INFO] Application des correctifs sur PQC..."

# Patch 1: src/Tools/tools.cpp - Garder l'inclusion de immintrin.h pour x86 uniquement
TOOLS_FILE="$PQC_SRC_DIR/src/Tools/tools.cpp"
# On vérifie si le fichier contient déjà le correctif pour éviter de l'appliquer deux fois
if ! grep -q "defined(__x86_64__)" "$TOOLS_FILE"; then
    echo "[INFO] Patching tools.cpp pour compatibilité ARM64..."
    # On remplace l'include simple par un bloc ifdef
    sed -i.bak 's/#include <immintrin.h>/#if defined(__x86_64__) || defined(_M_X64)\n#include <immintrin.h>\n#endif/' "$TOOLS_FILE"
fi

# Patch 2: CMakeLists.txt - Ajout des chemins d'include pour FLINT et GF2X
CMAKE_FILE="$PQC_SRC_DIR/CMakeLists.txt"
if ! grep -q "target_include_directories(pqc-static-lib PUBLIC \${FLINT_INCLUDE_DIRS})" "$CMAKE_FILE"; then
    echo "[INFO] Patching CMakeLists.txt pour lier correctement FLINT et GF2X..."
    
    # On utilise perl pour un remplacement multiligne plus robuste que sed
    # On remplace les anciennes lignes de link par des versions avec include directories explicités
    perl -i.bak -0777 -pe 's/target_link_libraries\(pqc-static-lib \$\{FLINT_STATIC_LIBRARIES\}\)\n\s*target_link_libraries\(pqc-static-lib \$\{GF2X_STATIC_LIBRARIES\}\)/target_include_directories(pqc-static-lib PUBLIC \$\{FLINT_INCLUDE_DIRS\})\ntarget_link_libraries(pqc-static-lib \$\{FLINT_STATIC_LIBRARIES\})\ntarget_include_directories(pqc-static-lib PUBLIC \$\{GF2X_INCLUDE_DIRS\})\ntarget_link_libraries(pqc-static-lib \$\{GF2X_STATIC_LIBRARIES\})/s' "$CMAKE_FILE"
fi

echo "[INFO] Configuration de PQC..."
mkdir -p "$PQC_SRC_DIR/build"
cd "$PQC_SRC_DIR/build"

# On nettoie le cache CMake pour être sûr de prendre en compte les nouveaux chemins
rm -f CMakeCache.txt

# Appel de CMake avec NTL_DIR défini
export NTL_DIR="$INSTALL_PREFIX"
cmake .. -DCMAKE_INSTALL_PREFIX="$PQC_INSTALL_DIR" \
    -DCMAKE_PREFIX_PATH="$INSTALL_PREFIX"

echo "[INFO] Compilation de PQC..."
make -j"$CORES"

echo "[INFO] Installation de PQC..."
make install

echo ""
echo "=============================================================================="
echo " Installation terminée !"
echo " Librairies installées dans : $PQC_INSTALL_DIR"
echo " Dépendances installées dans : $INSTALL_PREFIX"
echo "=============================================================================="
