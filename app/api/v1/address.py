from fastapi import APIRouter
from pydantic import BaseModel

from app.services.address.address_service import normalize_address

router = APIRouter()


class AddressNormalizeRequest(BaseModel):
    raw_address: str


@router.post("/normalize")
async def normalize_address_endpoint(data: AddressNormalizeRequest):
    return normalize_address(data.raw_address)
