from fastapi import APIRouter

api_router = APIRouter()

# Import and include route modules when they are created
from . import auth
# from . import organizations, tickets, integrations, analytics, alerts, webhooks, sync

api_router.include_router(auth.router)
# api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
# api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
# api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
# api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
# api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
# api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
# api_router.include_router(sync.router, prefix="/sync", tags=["sync"])


@api_router.get("/status")
async def api_status():
    """API status endpoint"""
    return {"status": "API is running", "version": "v1"}
