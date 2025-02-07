from dotenv import load_dotenv
from requests.exceptions import JSONDecodeError

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi import Depends, Query, Response, status, Request, HTTPException
from pydantic import BaseModel
from service import upload_signed_doc_in_lead, search_lead_by_doc_id

router = APIRouter(prefix="/trustme", tags=["TrustMe"])

@router.post("/webhook")
async def webhook_trustme(request: Request):
    try:
        # Получаем данные из тела запроса
        data = await request.form()
        data_dict = dict(data)  # Преобразуем в обычный словарь для удобства
        example = {
            "contract_id": "wriuphbzi",
            "status": 3,
            "client": "77474078044",
            "contract_url": "www.tct.kz/uploader/wriuphbzi"
        }

        doc_id = data_dict["contract_id"]
        lead_data = search_lead_by_doc_id(doc_id)

        lead_id = lead_data['_embedded']['leads'][0]['id']

        if data_dict["status"] == 3:
            upload_signed_doc_in_lead(lead_id, doc_id)    
            return JSONResponse(content={"message": "successful"}, status_code=200)
        return JSONResponse(content={"message": "successful"}, status_code=200)
        
    except Exception as e:
        print("Что-то пошло не так при обработке:", str(e))
        return JSONResponse(content={"message": "Что-то пошло не так при обработке"}, status_code=500)

class ContractUpdate(BaseModel):
    contract_id: str
    status: int
    client: str
    contract_url: str


@router.post("/webhook/test")
async def webhook_trustme_test(contract_id: str, status: int = 3):
    try:
        example = {
            "contract_id": "wriuphbzi",
            "status": 3,
            "client": "77474078044",
            "contract_url": "www.tct.kz/uploader/wriuphbzi"
        }

        doc_id = contract_id
        lead_data = search_lead_by_doc_id(doc_id)

        lead_id = lead_data['_embedded']['leads'][0]['id']

        if status == 3:
            upload_signed_doc_in_lead(lead_id, doc_id)    
            return JSONResponse(content={"message": "successful"}, status_code=200)
        return JSONResponse(content={"message": "successful"}, status_code=200)
        
    except Exception as e:
        print("Что-то пошло не так при обработке:", str(e))
        return JSONResponse(content={"message": "Что-то пошло не так при обработке"}, status_code=500)
