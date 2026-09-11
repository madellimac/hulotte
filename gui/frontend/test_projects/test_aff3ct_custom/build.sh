#!/bin/bash
# Build script for test_aff3ct_custom

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"

mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

cmake .. \
    -DSTREAMPU_ROOT="/home/cleroux/PROJECTS/hulotte/streampu" \
+    -DAFF3CT_ROOT="/home/cleroux/PROJECTS/hulotte/aff3ct" \
    -DCMAKE_BUILD_TYPE=Release

make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

if [ $? -eq 0 ]; then
    echo ""
    echo "Build successful!"
    echo "Run: ./build/test_aff3ct_custom"
else
    echo "Build failed"
    exit 1
fi
