import os
import json
import random
import string
import logging
import pathlib
from datetime import datetime

import jwt
import dotenv
import requests
from dotenv import load_dotenv

from fastapi import FastAPI
from api import api_router

dotenv_path = pathlib.Path(__file__).parent /  ".env"
load_dotenv(dotenv_path=dotenv_path)

amo_api = os.getenv("AMO_API")
trustme_bearer_token = os.getenv("TRUSTME_API")
app = FastAPI()
app.include_router(api_router)


@app.get("/")
def test():
    return 'hello world'
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="194.32.140.135", reload=True)
    # uvicorn.run("main:app", host="localhost", reload=True)


