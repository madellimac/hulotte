#!/bin/bash
# Script de lancement unifié pour la GUI Hulotte (Backend FastAPI + Frontend React/Vite)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Détection de l'interpréteur Python avec uvicorn
PYTHON_CMD="python3"
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$(dirname "$SCRIPT_DIR")/.venv/bin/python" ]; then
    PYTHON_CMD="$(dirname "$SCRIPT_DIR")/.venv/bin/python"
fi

# Vérification des prérequis Python
if ! "$PYTHON_CMD" -c "import uvicorn, fastapi" 2>/dev/null; then
    echo "[ERREUR] uvicorn ou fastapi n'est pas installé dans l'environnement Python ($PYTHON_CMD)."
    echo "Installez les dépendances avec : $PYTHON_CMD -m pip install -r gui/backend/requirements.txt"
    exit 1
fi

# Vérification de npm
if ! command -v npm &>/dev/null; then
    echo "[ERREUR] npm n'est pas installé sur le système."
    exit 1
fi

# Fonction de vérification de disponibilité de port
check_port() {
    local port=$1
    if "$PYTHON_CMD" -c "import socket, sys; sys.exit(0 if socket.socket().connect_ex(('127.0.0.1', $port)) != 0 else 1)" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Vérifier les ports 8000 et 5173
if ! check_port 8000; then
    echo "[ERREUR] Le port 8000 est déjà utilisé. Arrêtez le processus occupant le port 8000 avant de relancer."
    exit 1
fi

if ! check_port 5173; then
    echo "[ERREUR] Le port 5173 est déjà utilisé. Arrêtez le processus occupant le port 5173 avant de relancer."
    exit 1
fi

echo "============================================================"
echo " Starting Hulotte GUI..."
echo "============================================================"

# Variables pour conserver les PIDs
BACKEND_PID=""
FRONTEND_PID=""

# Fonction de nettoyage lors de l'arrêt (Ctrl+C / SIGINT / SIGTERM / EXIT)
# BACKEND_PID/FRONTEND_PID sont des PID de session (via setsid) : ils sont donc
# aussi le PGID du groupe, ce qui permet de stopper leurs enfants (reloader, vite) via kill -TERM -PID.
cleanup() {
    trap - INT TERM EXIT
    echo ""
    echo "Stopping Hulotte GUI..."

    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill -TERM "-$BACKEND_PID" 2>/dev/null || kill -TERM "$BACKEND_PID" 2>/dev/null || true
    fi

    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill -TERM "-$FRONTEND_PID" 2>/dev/null || kill -TERM "$FRONTEND_PID" 2>/dev/null || true
    fi

    sleep 1

    # Forcer l'arrêt si un des groupes de processus est toujours actif
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill -KILL "-$BACKEND_PID" 2>/dev/null || kill -KILL "$BACKEND_PID" 2>/dev/null || true
    fi

    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill -KILL "-$FRONTEND_PID" 2>/dev/null || kill -KILL "$FRONTEND_PID" 2>/dev/null || true
    fi

    echo "✓ Hulotte GUI stopped."
    exit 0
}

trap cleanup INT TERM EXIT

# Lancement du Backend dans sa propre session (setsid) pour regrouper ses enfants (reloader Uvicorn)
echo "Starting Backend on http://localhost:8000 ..."
setsid "$PYTHON_CMD" -m uvicorn gui.backend.main:app --reload --port 8000 &
BACKEND_PID=$!

sleep 2

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[ERREUR] Échec du démarrage du backend."
    exit 1
fi

echo "✓ Backend started on http://localhost:8000"

# Lancement du Frontend dans sa propre session (setsid) pour regrouper ses enfants (processus vite de npm)
echo "Starting Frontend on http://localhost:5173 ..."
setsid bash -c "cd '$SCRIPT_DIR/gui/frontend' && exec npm run dev" &
FRONTEND_PID=$!

sleep 2

if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "[ERREUR] Échec du démarrage du frontend."
    exit 1
fi

echo "✓ Frontend started on http://localhost:5173"
echo ""
echo "Hulotte GUI is running."
echo "Press Ctrl+C to stop."
echo "============================================================"

# Attendre la fin des processus
wait $BACKEND_PID $FRONTEND_PID
