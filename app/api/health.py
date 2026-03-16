from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthy")
def health_check():
    return {"status": "Healthy"}


@router.get("/ready")
def readiness_check():
    return {"status": "Ready"}
