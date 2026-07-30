from fastapi import APIRouter

from app.modules.telegram.router import router as telegram_router
from app.modules.waha.health import router as waha_health_router
from app.modules.waha.router import router as waha_router


router = APIRouter()
router.include_router(waha_router)
router.include_router(waha_health_router)
router.include_router(telegram_router)

