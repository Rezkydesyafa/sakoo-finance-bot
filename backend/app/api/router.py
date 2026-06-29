from fastapi import APIRouter

from app.api.v1.router import router as v1_router


router = APIRouter()
router.include_router(v1_router)


@router.get("/", tags=["api"])
def api_root() -> dict[str, str]:
    return {"message": "Sakoo Finance Bot API"}
