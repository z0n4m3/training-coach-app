from fastapi import FastAPI
from app.api.routes import cycling_equipment, dev, health, performance, plans, sessions, sync

app = FastAPI(title="Training Coach API", version="0.1.0")
app.include_router(health.router)
app.include_router(dev.router)
app.include_router(sync.router)
app.include_router(sessions.router)
app.include_router(plans.router)
app.include_router(performance.router)
app.include_router(cycling_equipment.router)
