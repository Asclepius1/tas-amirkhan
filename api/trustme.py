from dotenv import load_dotenv
from requests.exceptions import JSONDecodeError

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi import Depends, Query, Response, status, Request, HTTPException

from service import change_lead_pipline_by_doc_status, search_lead_by_doc_id

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
        doc_status = data_dict['status']

        change_lead_pipline_by_doc_status(lead_id, doc_status)
        
        return JSONResponse(content={"message": "successful"}, status_code=200)
    except Exception as e:
        print("Что-то пошло не так при обработке:", str(e))
        return JSONResponse(content={"message": "Что-то пошло не так при обработке"}, status_code=500)
