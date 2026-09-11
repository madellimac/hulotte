import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router

app = FastAPI(
    title="Hulotte GUI Backend",
    description="REST API backend for Hulotte GUI V1",
    version="1.0.0"
)

# Enable CORS for Vite frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def read_root():
    return {"status": "ok", "app": "Hulotte GUI Backend", "docs": "/docs"}

if __name__ == "__main__":
    uvicorn.run("gui.backend.main:app", host="127.0.0.1", port=8000, reload=True)
