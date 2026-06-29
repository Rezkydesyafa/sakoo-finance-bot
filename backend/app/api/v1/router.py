from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.jobs.router import router as jobs_router
from app.modules.media.router import router as media_router
from app.modules.ocr.router import router as ocr_router
from app.modules.reports.router import router as reports_router
from app.modules.stt.router import router as stt_router
from app.modules.transactions.router import router as transactions_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(jobs_router)
router.include_router(media_router)
router.include_router(ocr_router)
router.include_router(reports_router)
router.include_router(stt_router)
router.include_router(transactions_router)

