import re
import os
import requests
import uuid
import urllib.parse
import pypdf

def download_file(file_url: str, format_: str = 'pdf') -> str|None:

    response = requests.get(file_url)
    if response.status_code == 200:
        file_path = f'{uuid.uuid4()}.{format_}'
        # cd = response.headers.get("Content-Disposition", "")
        # filename = None

        # match = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", cd)
        # if match:
            # filename = urllib.parse.unquote(match.group(1)).split('.')[0]
        with open(f"temp/{file_path}", 'wb') as f:
            f.write(response.content)
        return file_path
def merge_files(doc_file_url: str, smeta_file_url:str) -> str:
    
    doc_file_path = download_file(doc_file_url)
    smeta_file_path = download_file(smeta_file_url)

    if not doc_file_path or not smeta_file_path:
        raise Exception("Ошибка при загрузке файлов")
    
    reader = pypdf.PdfReader(smeta_file_path)
    writer = pypdf.PdfWriter(doc_file_path)
    for page in reader.pages:
        writer.add_page(page)
    result_path = f'{uuid.uuid4()}.pdf'
    writer.write(f"temp/{result_path}")
    os.remove(doc_file_path)
    os.remove(smeta_file_path)
    return result_path


if __name__ == "__main__":
    file_url = "https://docs.google.com/document/export?format=pdf&id=1CJ_QIviRUOYnFUkDbkTKfouqr_WUuRrKvKg0lXNUAAc"
    file, _ = download_file('https://drive-b.amocrm.ru/download/21e8a443-5420-54ed-be45-f3d7f3e92e21/aa7713be-c3f9-4f11-a5ce-c433fa3a4dfb/1-Divine-spetsifikatsiia-zakaza-2025.pdf')
    print(file)
    # file1 = "temp/Договор на покупку штор тест два.pdf"
    # file2 = "temp/1. Divine спецификация заказа 2025.pdf"
    # reader = pypdf.PdfReader(file2)
    # writer = pypdf.PdfWriter(file1)

    # for page in reader.pages:
    #     writer.add_page(page)
    # file_url = "temp/merged.pdf"
    # writer.write("temp/merged.pdf")
    # os.remove(file_url) if file_url.endswith('.pdf') else None