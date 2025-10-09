from api.amo import router as amo_router
from api.trustme import router as trustme_router
from api.files import router as files_router
from fastapi import APIRouter


api_router = APIRouter()
api_router.include_router(amo_router)
api_router.include_router(trustme_router)
api_router.include_router(files_router)