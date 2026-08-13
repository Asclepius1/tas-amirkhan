import re
import os
import requests
import uuid
import urllib.parse
import pypdf

import asyncio
from logger_config import get_logger

logger = get_logger(__name__)

def download_file(file_url: str, format_: str = 'pdf') -> str|None:
    logger.info('Downloading file from %s', file_url)
    try:
        response = requests.get(file_url, timeout=30)
    except requests.RequestException as e:
        logger.exception('Request error while downloading %s: %s', file_url, e)
        return None
    logger.debug('Download response status for %s: %s', file_url, response.status_code)
    if response.status_code == 200:
        file_path = f'temp/{uuid.uuid4()}.{format_}'
        try:
            with open(f"{file_path}", 'wb') as f:
                f.write(response.content)
            logger.info('Saved downloaded file to %s', file_path)
            return file_path
        except OSError as e:
            logger.exception('Failed to write downloaded file %s: %s', file_path, e)
            return None
    else:
        logger.error('Failed to download %s status=%s body=%s', file_url, response.status_code, getattr(response, 'text', None))
        return None

def append_page(writer: pypdf.PdfWriter, reader: pypdf.PdfReader):
    for page in reader.pages:
        writer.add_page(page)

def merge_files(doc_file_url: str, amo_files:list[str]) -> str:
    doc_file_path = download_file(doc_file_url)
    if not doc_file_path:
        logger.error('Document file download failed for url=%s', doc_file_url)
        raise Exception('Ошибка при загрузке файла договора')

    smeta_file_path = download_file(amo_files[0])
    if not smeta_file_path:
        logger.error('Smeta file download failed for url=%s', amo_files[0])
        try:
            if doc_file_path and os.path.exists(doc_file_path):
                os.remove(doc_file_path)
        except Exception:
            logger.warning('Failed to remove temp doc file %s', doc_file_path)
        raise Exception('Ошибка при загрузке файла сметы')

    try:
        reader = pypdf.PdfReader(smeta_file_path)
        writer = pypdf.PdfWriter(doc_file_path)
        append_page(writer, reader)

        if len(amo_files) > 1:
            third_file_path = download_file(amo_files[1])
            if not third_file_path:
                logger.error('Third file download failed for url=%s', amo_files[1])
                raise Exception('Ошибка при загрузке третьего файла')
            third_reader = pypdf.PdfReader(third_file_path)
            append_page(writer, third_reader)
            try:
                os.remove(third_file_path)
            except OSError:
                logger.warning('Could not remove temp third file %s', third_file_path)

        result_path = f'{uuid.uuid4()}.pdf'
        out_path = f'temp/{result_path}'
        try:
            writer.write(out_path)
        except Exception as e:
            logger.exception('Failed to write merged PDF to %s: %s', out_path, e)
            raise

        for p in (doc_file_path, smeta_file_path):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except OSError:
                logger.warning('Could not remove temp file %s', p)

        logger.info('*******Файлы успешно объединены в %s', result_path)
        return result_path
    except Exception:
        logger.exception('Error while merging files for doc=%s amo_files=%s', doc_file_url, amo_files)
        raise


if __name__ == "__main__":
    file_url = "https://docs.google.com/document/export?format=pdf&id=1CJ_QIviRUOYnFUkDbkTKfouqr_WUuRrKvKg0lXNUAAc"
    file_2_url = 'https://drive-b.amocrm.ru/download/21e8a443-5420-54ed-be45-f3d7f3e92e21/aa7713be-c3f9-4f11-a5ce-c433fa3a4dfb/1-Divine-spetsifikatsiia-zakaza-2025.pdf'
    res = merge_files(file_url, file_2_url)
    logger.info(res)