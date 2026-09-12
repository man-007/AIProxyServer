from fastapi import APIRouter

from proxy_gateway.api.routes import config, health, messages, metrics, models

router = APIRouter()
router.include_router(health.router)
router.include_router(models.router)
router.include_router(messages.router)
router.include_router(metrics.router)
router.include_router(config.router)
