#!/bin/bash
# Build script for test_aff3ct

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"

mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

cmake .. \
    -DSTREAMPU_ROOT="/Users/cleroux/Documents/work/recherche/PROJECT/hulotte/streampu" \
    -DAFF3CT_ROOT="/Users/cleroux/Documents/work/recherche/PROJECT/hulotte/aff3ct" \
    -DHULOTTE_ROOT="/Users/cleroux/Documents/work/recherche/PROJECT/hulotte" \
    -DCMAKE_BUILD_TYPE=Release

make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

if [ $? -eq 0 ]; then
    echo ""
    echo "Build successful!"
    echo "Run: ./build/test_aff3ct"
else
    echo "Build failed"
    exit 1
fi
