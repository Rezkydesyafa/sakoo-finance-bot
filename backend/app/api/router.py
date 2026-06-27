from fastapi import APIRouter


router = APIRouter(tags=["api"])


@router.get("/")
def api_root() -> dict[str, str]:
    return {"message": "Sakoo Finance Bot API"}
