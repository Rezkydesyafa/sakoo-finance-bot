from fastapi import APIRouter

from app.modules.channels.telegram.router import router as telegram_router
from app.modules.channels.waha.health import router as waha_health_router
from app.modules.channels.waha.router import router as waha_router


router = APIRouter()
router.include_router(waha_router)
router.include_router(waha_health_router)
router.include_router(telegram_router)

