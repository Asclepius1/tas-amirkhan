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

from logger_config import get_logger

logger = get_logger(__name__)

from merge_files import merge_files


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
F5_DOCUMENT_API = os.getenv("F5_DOCUMENT_API")
F5_DOCUMENT_URL = os.getenv("F5_DOCUMENT_URL")
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
    logger.debug("inserting_data_into_amo payload: %s", data)
    doc_url = data['data']['url']
    doc_id = data['data']['id']
    logger.info('начали вставку данных в сделку амо')
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
    
    logger.debug('запрос отправлен')
    try:
        response = requests.patch(url, headers=AMO_HEADER, json=data)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as exc:
        logger.error('запрос не дошел успешно %s', exc.response.text)
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
    logger.debug('downloaded file local name: %s', local_file_path)
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

    logger.info("Файл %s успешно загружен с session_id %s, uuid = %s имя файла = %s", file_name, session_id, part_data.get('uuid'), part_data.get('name'))

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
        response = requests.post(url, headers=AMO_HEADER, json=data, timeout=30)
        logger.info('upload_signed_doc_in_lead POST -> status=%s', response.status_code)
        response.raise_for_status()
        logger.debug('upload_signed_doc_in_lead response: %s', response.text)
        return response.text
    except requests.exceptions.RequestException as exc:
        logger.exception('Ошибка при отправке заметки в AMO: %s', exc)
        status_code = getattr(getattr(exc, 'response', None), 'status_code', 502)
        detail = getattr(getattr(exc, 'response', None), 'text', str(exc))
        raise HTTPException(status_code=status_code, detail=f"Ошибка запроса: {detail}")




def tern_off_button(lead_id: str, field_id: int = 1323805) -> dict:
    url = f"{API_URL_AMO}/api/v4/leads/{lead_id}"
    
    data = {
        "custom_fields_values": [
            {
                "field_id": field_id,
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


def get_file_uuid_by_lead_id(lead_id: str, need_two_files: bool = False) -> list[str]|None:
    url = f'{API_URL_AMO}/api/v4/leads/{lead_id}/files'
    try:
        response = requests.get(url=url, headers=AMO_HEADER, timeout=15)
    except requests.RequestException as e:
        logger.exception('Request error when fetching file uuids for lead_id=%s: %s', lead_id, e)
        return [None, None]

    logger.debug('get_file_uuid_by_lead_id %s -> status=%s', url, response.status_code)
    if response.status_code != 200:
        # log body to help debugging when AMO returns 4xx/5xx
        logger.error('Non-200 response fetching files for lead_id=%s: status=%s body=%s', lead_id, response.status_code, getattr(response, 'text', None))
        return [None, None]

    try:
        data = response.json()
    except ValueError:
        logger.exception('Failed to parse JSON response for lead_id=%s: %s', lead_id, getattr(response, 'text', None))
        return [None, None]

    logger.debug('AMO files payload for lead_id=%s: %s', lead_id, data)
    files = data.get('_embedded', {}).get('files', [])
    if not files:
        logger.warning('No files embedded for lead_id=%s payload=%s', lead_id, data)
        return [None, None]

    # извлекаем до двух uuid и логируем отсутствие у конкретного файла
    first_uuid = files[0].get('file_uuid') if isinstance(files[0], dict) else None
    if not first_uuid:
        logger.warning('Missing file_uuid in first file entry for lead_id=%s entry=%s', lead_id, files[0])

    second_uuid = None
    if need_two_files:
        if len(files) < 2:
            logger.warning('Requested two files but only %s present for lead_id=%s', len(files), lead_id)
        else:
            second_uuid = files[1].get('file_uuid') if isinstance(files[1], dict) else None
            if not second_uuid:
                logger.warning('Missing file_uuid in second file entry for lead_id=%s entry=%s', lead_id, files[1])

    logger.debug('Extracted uuids for lead_id=%s: first=%s second=%s', lead_id, first_uuid, second_uuid)
    return [first_uuid, second_uuid]

def get_file_url_by_uuid(files_uuid: list[str]) -> list[str]|None:
    files_url = []
    for file_uuid in files_uuid:
        url = f'{API_URL_FILE_AMO}/v1.0/files/{file_uuid}'
        response = requests.get(url, headers=AMO_HEADER)
        logger.debug('get_file_url_by_uuid %s -> status=%s', url, response.status_code)
        try:
            data = response.json()
        except ValueError:
            logger.error('Failed to parse JSON when fetching file url for %s: %s', file_uuid, getattr(response, 'text', None))
            continue
        if '_links' in data:
            files_url.append(data['_links']['download']['href'])
        else:
            logger.warning('No download link for file_uuid=%s response=%s', file_uuid, data)
    return files_url


#--------trustme-----------
def get_trustme_data_by_lead_id(lead_id: str) -> dict:
    raw_data = get_data_from_amo_by_id('leads', lead_id)
    # companies_id = raw_data['_embedded']['companies'][0]['id']
    contacts_id = raw_data['_embedded']['contacts'][0]['id']
    contacts_data = get_data_from_amo_by_id('contacts', contacts_id)
    # companies_data = get_data_from_amo_by_id('companies', companies_id) 

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
    logger.debug("Сами реквизиты: %s", data)
    return data

def trustme_upload_with_file_url(lead_id: str, several_documents: bool = False) -> str:
    tern_off_button(lead_id)
    if several_documents:
        tern_off_button(lead_id, field_id=1334191)
    url = 'https://test.trustme.kz/trust_contract_public_apis/UploadWithFileURL?auto_sign=1'
    logger.info('check - trustme upload start')
    # Метод для amo документов 
    files_uuid = get_file_uuid_by_lead_id(lead_id, need_two_files=several_documents)
    logger.debug('Retrieved file UUIDs for lead_id=%s: %s', lead_id, files_uuid)
    amo_files_url = None
    if files_uuid:
        # фильтруем пустые/None uuid и логируем ситуацию
        filtered_files_uuid = [u for u in files_uuid if u]
        if len(filtered_files_uuid) != len(files_uuid):
            logger.warning('Some file UUIDs were empty for lead_id=%s original=%s filtered=%s', lead_id, files_uuid, filtered_files_uuid)
        if filtered_files_uuid:
            amo_files_url = get_file_url_by_uuid(filtered_files_uuid)
        else:
            amo_files_url = []
    # ------------------------
    
    # Метод для amo документов 
    lead_id_int = int(lead_id) 
    doc = get_doc_id_by_f5(lead_id_int)
    doc_id = doc.get('id')
    file_name = doc.get('name')
    file_url = get_doc_url_by_id(doc_id, format='pdf')
    #------------------------

    # Метод для объединения сметы и договора
    file_path = None
    if file_url and amo_files_url:
        try:
            logger.info('Merging files: doc_url=%s amo_files_count=%s', file_url, len(amo_files_url))
            file_path = merge_files(file_url, amo_files_url)
            file_url = f'http://82.115.43.124:8000/files/download/{file_path}'
            logger.info('Merge result file_path=%s', file_path)
        except Exception as e:
            logger.exception('Ошибка при объединении файлов для lead_id=%s: %s', lead_id, e)
            # Продолжаем без объединения — используем исходный file_url если есть
            file_path = None
    else:
        logger.debug('Skipping merge: file_url=%s amo_files_url=%s', file_url, amo_files_url)
    #------------------------

    values = {
        "downloadURL": file_url,
        "KzBmg": False,
        "FaceId":False,
        "requisites": [get_trustme_data_by_lead_id(lead_id)],
        "contractName": file_name
    }
    logger.debug('получили ревизиты summary: contractName=%s downloadURL=%s requisites=%s', file_name, file_url, bool(values.get('requisites')))
    headers = {
        'Content-Type': 'application/json',
        'Authorization': '{}'.format(TRUSTME_BEARER_TOKEN)
    }
    # Логируем предстоящий запрос и отправляем его
    logger.info('Sending request to TrustMe url=%s payload_keys=%s', url, list(values.keys()))
    try:
        response = requests.post(url, json=values, headers=headers, timeout=30)
        logger.info('TrustMe POST %s -> status=%s', url, response.status_code)
    except requests.RequestException as e:
        logger.exception('Ошибка запроса к TrustMe: %s', e)
        return JSONResponse(content={"message": "Ошибка при обращении к trustme"}, status_code=502)

    try:
        data = response.json()
    except ValueError as e:
        logger.error('Не удалось распарсить JSON от TrustMe: %s; response_text=%s', e, getattr(response, 'text', None))
        return JSONResponse(content={"message": "Ошибка парсинга ответа trustme"}, status_code=502)
    if not data:
        logger.warning('нету данных для вставки')
        return JSONResponse(content={"message": "Не получилось получить данные с trustme"}, status_code=500)
    if data.get('status') == "Error":
        logger.error('trustme returned error: %s', data.get('errorText'))
        return data
    if os.path.exists(f'temp/{file_path}'):
        os.remove(f'temp/{file_path}')
        logger.info("Файл удалён")
    else:
        logger.warning("Файл не найден")
    return inserting_data_into_amo(data, lead_id)


def trustme_set_webhook():
    # hook_url = 'https://webhook.site/1d6f9989-d61e-4b7f-99a0-81fadd0ab321'
    hook_url = 'http://82.115.43.124:8000/trustme/webhook'
    url = 'https://test.trustme.kz/trust_contract_public_apis/SetHook'

    values = {
        "URL": hook_url
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': '{}'.format(TRUSTME_BEARER_TOKEN)
    }

    response = requests.post(url, json=values, headers=headers)
    logger.debug(response.text)
    return response.text

def get_custom_fields(lead_id = None):
    import pyperclip
    url = f'{API_URL_AMO}/api/v4/leads/custom_fields'
    response = requests.get(url=url, headers=AMO_HEADER)
    if response.status_code == 200:
        data = response.json()
        pyperclip.copy(f'{data}')
        # return data

def get_doc_id_by_f5(entity_id: int):
    headers = {
        'X-Api-Token': f'{F5_DOCUMENT_API}',
        'Content-Type': 'application/json'
    }
    response = requests.get(url=F5_DOCUMENT_URL, headers=headers)
    if response.status_code == 200:
        data:dict = response.json()
        documents = [
            doc for doc in data.get("data", {}).get("documents", [])
            if doc.get("entity_id") == entity_id
        ]
        last_doc = documents[-1] if documents else None
        return last_doc
    else:
        logger.error("Ошибка: %s - %s", response.status_code, response.text)

def get_doc_url_by_id(document_id: str, format: str = 'docx'):
    headers = {
        'X-Api-Token': f'{F5_DOCUMENT_API}',
        'Content-Type': 'application/json'
    }
    url = f'{F5_DOCUMENT_URL}/{document_id}'
    logger.debug(url)
    response = requests.get(url=f'{F5_DOCUMENT_URL}/{document_id}', headers=headers)
    if response.status_code == 200:
        data:dict = response.json()
        logger.debug('get_doc_url_by_id response data: %s', data)
        id = data.get('data').get('document').get('document_id')
        return f'https://docs.google.com/document/export?format={format}&id={id}'
    
if __name__ == "__main__":
    # 26231243
    trustme_upload_with_file_url('26231243')