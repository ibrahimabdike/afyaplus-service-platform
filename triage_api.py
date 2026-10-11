import logging
import os
from fastapi import FastAPI, HTTPException, Depends
from openai import OpenAI
from pydantic import BaseModel, Field
from auth import check_password, create_token, current_user

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("afyaplus.triage")

app = FastAPI(title="AfyaPlus Triage API", version="1.0.0")
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY", "not-configured"),
    base_url="https://openrouter.ai/api/v1",
) if os.getenv("OPENROUTER_API_KEY") else None

class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=128)

class TriageRequest(BaseModel):
    model_config = {"extra": "forbid"}
    patient_message: str = Field(min_length=5, max_length=1000)
    county: str = Field(min_length=2, max_length=40)

class TriageResponse(BaseModel):
    urgency: str
    advice: str
    model_used: str

@app.get("/health")
def health():
    return {"service": "triage-api", "version": "1.0.0", "status": "ok"}

@app.post("/token")
def login(body: LoginRequest):
    if not check_password(body.username, body.password):
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    return {"access_token": create_token(body.username), "token_type": "bearer"}

def run_triage(message: str, county: str) -> tuple[str, str, str]:
    urgent_words = ("chest pain", "heavy bleeding", "unconscious", "cannot breathe",
                    "difficulty breathing", "seizure")
    if any(word in message.lower() for word in urgent_words):
        return ("high", "Seek urgent medical care now or contact local emergency services.",
                "safety-rule-v1")
    if client is None:
        return ("unknown", "The AI service is not configured. Contact a qualified health worker.",
                "safe-stub-v1")
    try:
        result = client.chat.completions.create(
            model=os.getenv("TRIAGE_MODEL", "openai/gpt-4o-mini"),
            messages=[
                {"role": "system", "content":
                 "You are an AfyaPlus community health information assistant. "
                 "Do not diagnose, prescribe, or recommend medication doses. "
                 "If severe or emergency symptoms are described, advise urgent professional care. "
                 "Return concise plain language, and do not claim certainty."},
                {"role": "user", "content":
                 f"County: {county}\nPatient message: {message}\n"
                 "Give general next-step guidance, not a diagnosis."},
            ],
            max_tokens=180, temperature=0.2,
        )
        advice = result.choices[0].message.content or ""
        return ("moderate", advice[:1200], "openrouter")
    except Exception:
        log.exception("model_call_failed")
        raise HTTPException(status_code=503, detail="The AI service is temporarily unavailable.")

@app.get("/coordinator/status")
def coordinator_status(user: dict = Depends(current_user)):
    # Demonstrates role-based authorization: authenticated non-coordinators receive 403.
    if user["role"] != "coordinator":
        raise HTTPException(status_code=403, detail="Coordinator role required.")
    return {"status": "ok", "message": "Coordinator access granted."}

@app.post("/triage", response_model=TriageResponse)
def triage(body: TriageRequest, user: dict = Depends(current_user)):
    urgency, advice, model_used = run_triage(body.patient_message, body.county)
    log.info("event=triage user=%s county=%s model=%s", user["sub"], body.county, model_used)
    return TriageResponse(urgency=urgency, advice=advice, model_used=model_used)
