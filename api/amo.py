from dotenv import load_dotenv
from requests.exceptions import JSONDecodeError

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi import Depends, Query, Response, status, Request, HTTPException

from service import trustme_upload_with_file_url, tern_off_button

router = APIRouter(prefix="/amo", tags=["Amo"])

@router.post("/check")
async def check(request: Request):
    """
    Пока не работает, нужен для того чтобы вручную обновлять данные с trustme в amo
    """
    try:
        data = await request.form()
        data_dict = dict(data)
        lead_id = str(data_dict.get('leads[add][0][id]', ''))
        print(data_dict)
        tern_off_button(lead_id)
        if not lead_id:
            return JSONResponse(content={"message": "Не получилось получить lead_id"}, status_code=500)
        response = trustme_upload_with_file_url(lead_id)
        if response.get('status') == "Error":
            return JSONResponse(content={"message": f"{data.get('errorText')}"}, status_code=500)
        return JSONResponse(content={"message": "Webhook received successfully"}, status_code=200)
    except:
        return JSONResponse(content={"message": "Что-то пошло не так при обработке"}, status_code=500)


@router.post("/webhook")
async def amo_webhook(request: Request):
    try:
        data = await request.form()
        data_dict = dict(data)
        lead_id = str(data_dict.get('leads[add][0][id]', ''))
        print(lead_id)
        if not lead_id:
            return JSONResponse(content={"message": "Не получилось получить lead_id"}, status_code=501)
        trustme_upload_with_file_url(lead_id)
        return JSONResponse(content={"message": "Webhook received successfully"}, status_code=200)
    except:
        return JSONResponse(content={"message": "Что-то пошло не так при обработке"}, status_code=502)
