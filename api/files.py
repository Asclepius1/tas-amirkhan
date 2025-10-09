import re
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(prefix="/files", tags=["Files"])

@router.get("download/{file_name}")
def download_file(file_name: str):
    file_path = f'temp/{file_name}'
    # orig_name = re.search(r"(.*)\_\_\_", file_name).group(1)
    return FileResponse(path=file_path, media_type='application/octet-stream')
