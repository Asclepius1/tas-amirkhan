from dotenv import load_dotenv
from requests.exceptions import JSONDecodeError

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi import Depends, Query, Response, status, Request, BackgroundTasks

from service import trustme_upload_with_file_url, tern_off_button, parse_nested_keys

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
        lead_id = str(data_dict.get('leads[status][0][id]', ''))
        if not lead_id:
            lead_id = str(data_dict.get('leads[add][0][id]', ''))
            if not lead_id:
                return JSONResponse(content={"message": "Не получилось получить lead_id"}, status_code=404)
        trustme_upload_with_file_url(lead_id)
        return JSONResponse(content={"message": "Webhook received successfully"}, status_code=200)
    except:
        return JSONResponse(content={"message": "Что-то пошло не так при обработке"}, status_code=502)

@router.post("/webhook-test")
async def amo_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.form()
        data_dict = dict(data)
        structured_data = parse_nested_keys(data_dict)
        custom_fields = structured_data["leads"]["update"][0]["custom_fields"]
        for d in custom_fields:
            if d['id'] == '1323805':
                if d['values'][0]['value'] == '1':
                    lead_id = structured_data["leads"]["update"][0]["id"]
                    background_tasks.add_task(trustme_upload_with_file_url, lead_id)
                    return JSONResponse(content={"message": "Webhook received successfully"}, status_code=202)
        return JSONResponse(content={"message": "Webhook received successfully"}, status_code=200)


    except:
        return JSONResponse(content={"message": "Что-то пошло не так при обработке"}, status_code=203)
