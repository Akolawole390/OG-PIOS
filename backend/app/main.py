from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import (
    administration,
    ai_insights,
    alerts,
    auth,
    cost_revenue,
    equipment,
    health,
    maintenance,
    operating_costs,
    production,
    production_import,
    production_loss,
    reports,
    settings as settings_router,
    users,
    wells,
    what_if,
)

settings = get_settings()

app = FastAPI(title="OG-PIOS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(wells.router)
app.include_router(wells.facilities_router)
app.include_router(production.router)
app.include_router(production_import.router)
app.include_router(settings_router.router)
app.include_router(equipment.router)
app.include_router(maintenance.router)
app.include_router(production_loss.router)
app.include_router(operating_costs.router)
app.include_router(cost_revenue.router)
app.include_router(alerts.router)
app.include_router(ai_insights.router)
app.include_router(what_if.router)
app.include_router(reports.router)
app.include_router(users.router)
app.include_router(administration.router)
