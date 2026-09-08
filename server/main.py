'''
Activate virtual environment: source env/bin/activate
To run server: uvicorn main:app --reload       
'''

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
# import openai
from dotenv import load_dotenv
import os
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from google.cloud import speech_v1p1beta1 as speech
import uuid
import time

from generate_text import generate_text
from generate_speech import text_to_speech
from utils import check_string_length
# from twilio.operations import get_recording

load_dotenv()

account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_number = os.getenv('TWILIO_PHONE_NUMBER')

# openai.api_key = os.getenv('OPENAI_API_KEY')

eleven_labs_api_key = os.getenv('ELEVEN_LABS_API_KEY')

special_secret = os.getenv('SPECIAL_SECRET')
public_base_url = os.getenv('PUBLIC_BASE_URL')

client = Client(account_sid, auth_token)

class RequestModel(BaseModel):
    id: str
    prompt: str
    tone: str
    phoneNumber: str
    purpose: str
    voice: str
    lengthOfCall: str
    stability: float
    similarity: float

app = FastAPI()

origins = [
       "http://localhost:3000",
       "http://127.0.0.1:3000", 
       "http://localhost:8000",
       "http://127.0.0.1:8000",
       "*"  # This should be there
   ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/audio/{filename}")
async def get_audio(filename: str):
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".mp3"):
        raise HTTPException(status_code=404, detail="Not found")
    path = os.path.join(os.path.dirname(__file__), safe_name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type="audio/mpeg")

@app.post("/start-call")
async def start_call(req: RequestModel, background_tasks: BackgroundTasks):
    data = req.dict()

    # check if the special secret is provided shhhhh :)
    if special_secret and data["purpose"].lower() == special_secret:
        call_text = data["prompt"]
    else:
        call_text = generate_text(data["prompt"], data["tone"], data["purpose"], data["lengthOfCall"])

    check_string_length(call_text, 10000)

    print(call_text)

    audio_file = text_to_speech(call_text, data["voice"], eleven_labs_api_key, data["stability"], data["similarity"])

    if not public_base_url:
        raise HTTPException(status_code=500, detail="PUBLIC_BASE_URL is not set - start a tunnel and set it in .env")
    file_path = f"{public_base_url}/audio/{os.path.basename(audio_file)}"
    print(file_path)
    twiml = VoiceResponse()
    twiml.pause(length=1) # 2 sec delay
    twiml.play(file_path)
    # twiml.record(play_beep=False)

    call = client.calls.create(
            to=req.phoneNumber,
            from_=twilio_number,
            twiml=twiml,
            # status_callback=f'https://d1d8-192-12-181-163.ngrok-free.app/call-status?id={data["id"]}',  # Add this line
            # status_callback_event=['completed']  # Add this line
    )

    return {"message": "Call initiated", "call_sid": call.sid}

# @app.post("/call-status")
# async def call_status(request: Request):
#     form_data = await request.form()
#     # print(form_data)
#     # print(request)

#     id = request.query_params.get('id')
#     if not id:
#         raise HTTPException(status_code=400, detail="Missing 'id' query parameter")
    
#     call_sid = form_data.get('CallSid')

#     call = client.calls(call_sid).fetch()
#     recording_uri = call.media_url
#     print(call)

#     recording_url = f"https://api.twilio.com{recording_uri}".replace('.json', '.mp3')    
#     print(f"Recording URL: {recording_url}")

#     download_rec = requests.get(recording_url, auth=(account_sid, auth_token))
#     if download_rec.status_code != 200:
#         return JSONResponse(status_code=download_rec.status_code, content={"message": "Failed to download recording"})
    
#     print(download_rec)
#     local_filename = f"{uuid.uuid4()}-recording.mp3"
#     with open(local_filename, "wb") as f:
#         f.write(download_rec.content)
    
#     uploaded_url = upload_audio(local_filename, bucket)

#     update_recording_url(id, uploaded_url)

#     return JSONResponse(status_code=200, content={"recording_url": "recording_url"})