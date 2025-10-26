import re
import os
import requests
import uuid
import urllib.parse
import pypdf

import asyncio

def download_file(file_url: str, format_: str = 'pdf') -> str|None:
    response = requests.get(file_url)
    if response.status_code == 200:
        file_path = f'temp/{uuid.uuid4()}.{format_}'
        with open(f"{file_path}", 'wb') as f:
            f.write(response.content)
        return file_path

def append_page(writer: pypdf.PdfWriter, reader: pypdf.PdfReader):
    for page in reader.pages:
        writer.add_page(page)

def merge_files(doc_file_url: str, amo_files:list[str]) -> str:
    
    doc_file_path = download_file(doc_file_url)
    smeta_file_path = download_file(amo_files[0])

    if not doc_file_path or not smeta_file_path:
        raise Exception("Ошибка при загрузке файлов")
    
    reader = pypdf.PdfReader(smeta_file_path)
    writer = pypdf.PdfWriter(doc_file_path)
    append_page(writer, reader)

    if len(amo_files) > 1:
        third_file_path = download_file(amo_files[1])
        if not third_file_path:
            raise Exception("Ошибка при загрузке третьего файла")
        third_reader = pypdf.PdfReader(third_file_path)
        append_page(writer, third_reader)
        os.remove(third_file_path)
    
    result_path = f'{uuid.uuid4()}.pdf'
    writer.write(f"temp/{result_path}")
    os.remove(doc_file_path)
    os.remove(smeta_file_path)
    print(f"*******Файлы успешно объединены в {result_path}")
    return result_path


if __name__ == "__main__":
    file_url = "https://docs.google.com/document/export?format=pdf&id=1CJ_QIviRUOYnFUkDbkTKfouqr_WUuRrKvKg0lXNUAAc"
    file_2_url = 'https://drive-b.amocrm.ru/download/21e8a443-5420-54ed-be45-f3d7f3e92e21/aa7713be-c3f9-4f11-a5ce-c433fa3a4dfb/1-Divine-spetsifikatsiia-zakaza-2025.pdf'
    res = merge_files(file_url, file_2_url)
    print(res)