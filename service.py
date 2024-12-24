import os
import re
import json
import pathlib
from typing import List, Literal
import uuid

from fastapi.responses import JSONResponse
import requests
from dotenv import load_dotenv

from fastapi import HTTPException, Response


dotenv_path = pathlib.Path(__file__).parent /  ".env"
load_dotenv(dotenv_path=dotenv_path)

trustme_bearer_token = os.getenv("TRUSTME_API")
api_url_amo = os.getenv("API_URL_AMO")
api_url_file_amo = 'https://drive-b.amocrm.ru'
api_token_amo = os.getenv("AMO_API")
pipline_id = int(os.getenv("PIPLINE_ID"))
status_id_signed = int(os.getenv("STATUS_ID_SIGNED"))
status_id_signed_by_the_client = int(os.getenv("STATUS_ID_SIGNED_BY_THE_CLIENT"))
status_id_signed_by_the_company = int(os.getenv("STATUS_ID_SIGNED_BY_THE_COMPANY"))


#------общие----------
def format_phone_number(phone: str) -> str:
    # Удаляем все символы, кроме цифр
    digits = re.sub(r'\D', '', phone)

    # Проверяем, начинается ли номер с 8 или 7, или содержит меньше 10 цифр
    if len(digits) < 10:
        return f"Некорректный номер: {phone}"

    # Если номер начинается с 8, заменяем на 7
    if digits.startswith('8'):
        digits = '7' + digits[1:]
    elif not digits.startswith('7'):
        digits = '7' + digits

    # Оставляем только первые 11 символов
    formatted_number = f"+{digits[:11]}"

    return formatted_number

#------amo-----
def get_data_from_amo_by_id(type: Literal['leads', 'contacts', 'companies'], id: str) -> dict:
    url = f"{api_url_amo}/api/v4/{type}/{id}"
    headers = {"Authorization": f"Bearer {api_token_amo}"}
    params = {
        "with": 'contacts'
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Проверка на успешный статус
        data = response.json()
        return data
    except requests.exceptions.HTTPError as exc:
        # Обработка HTTP ошибок
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка запроса: {exc.response.text}")


def inserting_data_into_amo(data: dict, lead_id: str) -> str:
    print(data)
    doc_url = data['data']['url']
    doc_id = data['data']['id']
    print('начали вставку данных в сделку амо')
    url = f"{api_url_amo}/api/v4/leads/{lead_id}"
    data = {
        "custom_fields_values":[
            {
                "field_id": 1323459,
                "values": [
                    {
                        "value": f"{doc_id}"
                    }
                ]
            },
            {
                "field_id": 1323463,
                "values": [
                    {
                        "value": f"{doc_url}"
                    }
                ]
            },
        ]
    }
    headers = {"Authorization": f"Bearer {api_token_amo}"}
    print('запрос отправлен')
    try:
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as exc:
        print(f'запрос не дошел успешно {exc.response.text}')
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка запроса: {exc.response.text}")


def search_lead_by_doc_id(doc_id: str) -> dict:
    url = f"{api_url_amo}/api/v4/leads"
    params = {
        'limit': 1,
        'query':doc_id
    }
    headers = {"Authorization": f"Bearer {api_token_amo}"}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.HTTPError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка запроса: {exc.response.text}")

def change_lead_pipline_by_doc_status(lead_id: int|str, doc_status: int) -> str|HTTPException:
    url = f"{api_url_amo}/api/v4/leads/{lead_id}"
    headers = {"Authorization": f"Bearer {api_token_amo}"}
    if doc_status == 0:
        pass
    elif doc_status == 1:
        data = {'status_id':status_id_signed_by_the_company}
    elif doc_status == 2:
        data = {'status_id':status_id_signed_by_the_client}
    elif doc_status == 3:
        data = {'status_id':status_id_signed}
    
    try:
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка запроса: {exc.response.text}")

def tern_off_button(lead_id: str) -> dict:
    url = f"{api_url_amo}/api/v4/leads/{lead_id}"
    headers = {"Authorization": f"Bearer {api_token_amo}"}
    data = {
        "custom_fields_values": [
            {
                "field_id": 1323805,
                "values": [
                    {
                        "value": False  # Отключение checkbox
                    }
                ]
            }
        ]
    }
    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as exc:
        # Обработка HTTP ошибок
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка запроса: {exc.response.text}")

def normalize_nested_keys(data):
    if isinstance(data, dict):
        # Проверяем, все ли ключи числовые, чтобы превратить их в список
        if all(k.isdigit() for k in data.keys()):
            return [normalize_nested_keys(data[k]) for k in sorted(data, key=int)]
        # Рекурсивно обрабатываем вложенные словари
        return {k: normalize_nested_keys(v) for k, v in data.items()}
    return data  

def parse_nested_keys(data):
    result = {}
    for key, value in data.items():
        keys = key.replace(']', '').split('[')  # Разбиваем ключ по уровням
        current = result
        for k in keys[:-1]:  # Создаем вложенные словари
            current = current.setdefault(k, {})
        current[keys[-1]] = value  # Устанавливаем значение
    return normalize_nested_keys(result)


def get_file_uuid_by_lead_id(lead_id: str) -> str|None:

    url = f'{api_url_amo}/api/v4/leads/{lead_id}/files'
    headers = {"Authorization": f"Bearer {api_token_amo}"}
    response = requests.get(url=url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        first_uuid = data['_embedded']['files'][0].get('file_uuid', '')
        return first_uuid
    return None

def get_file_url_by_uuid(file_uuid: str):

    url = f'{api_url_file_amo}/v1.0/files/{file_uuid}'
    headers = {"Authorization": f"Bearer {api_token_amo}"}
    response = requests.get(url, headers=headers)
    data = response.json()
    file_url = data['_links']['download']['href']
    return file_url


#--------trustme-----------
def get_trustme_data_by_lead_id(lead_id: str) -> dict:
    raw_data = get_data_from_amo_by_id('leads', lead_id)
    companies_id = raw_data['_embedded']['companies'][0]['id']
    contacts_id = raw_data['_embedded']['contacts'][0]['id']
    contacts_data = get_data_from_amo_by_id('contacts', contacts_id)
    companies_data = get_data_from_amo_by_id('companies', companies_id) 

    companies_custom_fields = companies_data.get('custom_fields_values', [])
    bin_iin_values = [
        v['value']
        for field in companies_custom_fields
        if field.get('field_id') == 1322681
        for v in field.get('values', [])
    ]

    contacts_custom_fields = contacts_data.get('custom_fields_values', [])
    phone = [
        v['value']
        for field in contacts_custom_fields
        if field.get('field_id') == 1320119
        for v in field.get('values', [])
    ]



    data = {
        "CompanyName":companies_data['name'],
        "FIO":contacts_data['name'],
        "IIN_BIN": bin_iin_values[0] if bin_iin_values else '',
        "PhoneNumber": format_phone_number(phone[0]) if phone else ''
    }
    print(f"Сами реквизиты: {data}")
    return data


async def trustme_upload_with_file_url(
        lead_id: str, 
        # file_url: str = "https://drive-b.amocrm.ru/download/21e8a443-5420-54ed-be45-f3d7f3e92e21/c329ce74-0eaf-4b55-a6e2-3c2c81a175b4/DOGOVOR-na-vnedrenie-2.docx"
        ) -> str:
    tern_off_button(lead_id)
    bearer_token = trustme_bearer_token
    url = 'https://test.trustme.kz/trust_contract_public_apis/UploadWithFileURL'
    print('check - trustme upload start')
    
    file_uuid = get_file_uuid_by_lead_id(lead_id)
    if not file_uuid:
        return
    file_url = get_file_url_by_uuid(file_uuid)

    values = {
        "downloadURL": file_url,
        "KzBmg": False,
        "FaceId":False,
        "requisites": [get_trustme_data_by_lead_id(lead_id)],
        "contractName": "test"
    }
    print('получили ревизиты')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer {}'.format(bearer_token)
    }

    response = requests.post(url, json=values, headers=headers)
    print(f'запрос на создание файл получен: {response}, \n{response.text}')
    data = response.json()
    if not data:
        print('нету данных для вставки')
        return JSONResponse(content={"message": "Не получилось получить данные с trustme"}, status_code=500)
    if data.get('status') == "Error":
        print(data.get("errorText"))
        return data
    return inserting_data_into_amo(data, lead_id)


def trustme_set_webhook():
    hook_url = 'https://webhook.site/1d6f9989-d61e-4b7f-99a0-81fadd0ab321'
    url = 'https://test.trustme.kz/trust_contract_public_apis/SetHook'

    values = {
        "URL": hook_url
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer {}'.format(trustme_bearer_token)
    }

    response = requests.post(url, json=values, headers=headers)

    print(response.text)
    return response.text


if __name__ == "__main__":
    # print(trustme_upload_with_file_url('23682805'))
    # trustme_set_webhook()
    # data = search_lead_by_doc_id("wriuphbzi")
    # data['_embedded']['leads'][0]['id']
    # change_lead_pipline_by_doc_status(23720189, 3)
    # print(get_file_url_by_uuid(get_file_uuid_by_lead_id('23682805')))
    pass
    