#!/bin/bash
# Build script for test_hw

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"

mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

cmake .. \
    -DSTREAMPU_ROOT="/home/cleroux/PROJECTS/hulotte/streampu" \
    -DCMAKE_PREFIX_PATH="/usr/local/share/verilator" \
    -DCMAKE_BUILD_TYPE=Release

make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

if [ $? -eq 0 ]; then
    echo ""
    echo "Build successful!"
    echo "Run: ./build/test_hw"
else
    echo "Build failed"
    exit 1
fi
