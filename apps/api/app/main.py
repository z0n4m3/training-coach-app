from fastapi import FastAPI
from app.api.routes import dev, health, sessions, sync

app = FastAPI(title="Training Coach API", version="0.1.0")
app.include_router(health.router)
app.include_router(dev.router)
app.include_router(sync.router)
app.include_router(sessions.router)
