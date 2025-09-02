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

TRUSTME_BEARER_TOKEN = os.getenv("TRUSTME_API")
API_URL_AMO = os.getenv("API_URL_AMO")
API_URL_FILE_AMO = 'https://drive-b.amocrm.ru'
API_TOKEN_AMO = os.getenv("AMO_API")
PIPLINE_ID = int(os.getenv("PIPLINE_ID"))
STATUS_ID_SIGNED = int(os.getenv("STATUS_ID_SIGNED"))
STATUS_ID_SIGNED_BY_THE_CLIENT = int(os.getenv("STATUS_ID_SIGNED_BY_THE_CLIENT"))
STATUS_ID_SIGNED_BY_THE_COMPANY = int(os.getenv("STATUS_ID_SIGNED_BY_THE_COMPANY"))
AMO_HEADER = {"Authorization": f"Bearer {API_TOKEN_AMO}"}

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
    url = f"{API_URL_AMO}/api/v4/{type}/{id}"
    
    params = {
        "with": 'contacts'
    }
    try:
        response = requests.get(url, headers=AMO_HEADER, params=params)
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
    url = f"{API_URL_AMO}/api/v4/leads/{lead_id}"
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
    
    print('запрос отправлен')
    try:
        response = requests.patch(url, headers=AMO_HEADER, json=data)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as exc:
        print(f'запрос не дошел успешно {exc.response.text}')
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка запроса: {exc.response.text}")


def search_lead_by_doc_id(doc_id: str) -> dict:
    url = f"{API_URL_AMO}/api/v4/leads"
    params = {
        'limit': 1,
        'query':doc_id
    }
    

    try:
        response = requests.get(url, headers=AMO_HEADER, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.HTTPError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка запроса: {exc.response.text}")

def upload_file_into_amo_file_data(file_url: str):
    # Шаг 1. Скачиваем файл из облака
    # local_file_path = file_url.split('/')[-1]
    response = requests.get(file_url, stream=True)
    local_file_path = response.headers.get('Content-Disposition')
    filename_regex = r'filename=(?P<filename>[^;]+)'
    match = re.search(filename_regex, local_file_path)
    if match:
        local_file_path = match.group('filename')
    print(local_file_path)
    response.raise_for_status()
    with open(local_file_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    file_size = os.path.getsize(local_file_path)
    file_name = os.path.basename(local_file_path)
    content_type = response.headers.get('Content-Type', 'application/octet-stream')

    # Шаг 2. Создаем сессию загрузки
    session_payload = {
        "file_name": file_name,
        "file_size": file_size,
        "content_type": content_type
    }
    session_response = requests.post(f"{API_URL_FILE_AMO}/v1.0/sessions", json=session_payload, headers=AMO_HEADER)
    session_response.raise_for_status()
    session_data = session_response.json()

    session_id = session_data["session_id"]
    upload_url = session_data["upload_url"]
    max_part_size = session_data["max_part_size"]

    # Шаг 3. Разделяем файл на части и загружаем
    with open(local_file_path, 'rb') as f:
        part_number = 0
        while chunk := f.read(max_part_size):
            part_response = requests.post(upload_url, data=chunk, headers=AMO_HEADER)
            part_response.raise_for_status()
            part_data = part_response.json()
            upload_url = part_data.get("next_url")
            part_number += 1

    # Шаг 4. Получаем результат загрузки
    if part_number == 0:
        raise Exception("Файл не был загружен")

    # print(f"Файл {file_name} успешно загружен с session_id {session_id}, uuid = {part_data['uuid']} имя файла = {part_data['name']}")

    # Удаляем локально сохраненный файл
    os.remove(local_file_path)
    return part_data['uuid'], file_name

def upload_signed_doc_in_lead(lead_id: int|str, doc_id:str) -> str|HTTPException:
    url = f"{API_URL_AMO}/api/v4/leads/{lead_id}/notes"
    doc_url = f"https://test.trustme.kz/trust_contract_public_apis/doc/DownloadContractFile/{doc_id}"
    file_uuid, filename = upload_file_into_amo_file_data(doc_url)
    data = [
        {
            'note_type': 'common',
            'params':{
                'text': 'Документ успешно получен'
            }
        },
        {
            'note_type':'attachment',
            "params": {
                "version_uuid": '',
                "file_uuid": file_uuid,
                "file_name": filename,
            },
    }]
    try:
        response = requests.post(url, headers=AMO_HEADER, json=data)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"Ошибка запроса: {exc.response.text}")




def tern_off_button(lead_id: str) -> dict:
    url = f"{API_URL_AMO}/api/v4/leads/{lead_id}"
    
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
        response = requests.patch(url, json=data, headers=AMO_HEADER)
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

    url = f'{API_URL_AMO}/api/v4/leads/{lead_id}/files'
    
    response = requests.get(url=url, headers=AMO_HEADER)
    if response.status_code == 200:
        data = response.json()
        first_uuid = data['_embedded']['files'][0].get('file_uuid', '')
        return first_uuid

def get_file_url_by_uuid(file_uuid: str) -> str|None:

    url = f'{API_URL_FILE_AMO}/v1.0/files/{file_uuid}'
    
    response = requests.get(url, headers=AMO_HEADER)
    data = response.json()
    if '_links' in data:
        file_url = data['_links']['download']['href']
        return file_url


#--------trustme-----------
def get_trustme_data_by_lead_id(lead_id: str) -> dict:
    raw_data = get_data_from_amo_by_id('leads', lead_id)
    # companies_id = raw_data['_embedded']['companies'][0]['id']
    contacts_id = raw_data['_embedded']['contacts'][0]['id']
    contacts_data = get_data_from_amo_by_id('contacts', contacts_id)
    # companies_data = get_data_from_amo_by_id('companies', companies_id) 

    # companies_custom_fields = companies_data.get('custom_fields_values', [])
    # bin_iin_values = [
    #     v['value']
    #     for field in companies_custom_fields
    #     if field.get('field_id') == 1322681
    #     for v in field.get('values', [])
    # ]

    contacts_custom_fields = contacts_data.get('custom_fields_values', [])
    phone = [
        v['value']
        for field in contacts_custom_fields
        if field.get('field_id') == 1320119
        for v in field.get('values', [])
    ]
    bin_iin_values = [
        v['value']
        for field in contacts_custom_fields
        if field.get('field_id') == 1323815
        for v in field.get('values', [])
    ]
    companiy_name = [
        v['value']
        for field in contacts_custom_fields
        if field.get('field_id') == 1322679
        for v in field.get('values', [])
    ]



    data = {
        # "CompanyName":companies_data['name'],
        "CompanyName":companiy_name[0] if companiy_name else '',
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
    bearer_token = TRUSTME_BEARER_TOKEN
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
        'Authorization': 'Bearer {}'.format(TRUSTME_BEARER_TOKEN)
    }

    response = requests.post(url, json=values, headers=headers)

    print(response.text)
    return response.text


if __name__ == "__main__":
    # print(trustme_upload_with_file_url('23682805'))
    # trustme_set_webhook()
    # data = search_lead_by_doc_id("wriuphbzi")
    # data['_embedded']['leads'][0]['id']
    upload_signed_doc_in_lead('23720189', '5tktfq644')
    # print(get_file_url_by_uuid('1ab735df-dd91-47eb-8c9e-93a4b76204ca'))
    # upload_file_into_amo_file_data('https://test.trustme.kz/trust_contract_public_apis/doc/DownloadContractFile/xf1ysrkdz')
    pass
    