from datetime import datetime

from fastapi import FastAPI, Request
import httpx
from fastapi import FastAPI
from fastapi import HTTPException
from sqlmodel import SQLModel, Field, Session, create_engine
from typing import Optional
import httpx


# 1. Setup Βάσης Δεδομένων (SQLite)
class HITLTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    agent_id: str
    context: str
    urgency: str  # low, medium, high
    status: str = "pending" # pending, approved, rejected 


sqlite_url = "sqlite:///database.db"
engine = create_engine(sqlite_url)

app = FastAPI()
#φτιαχνουμε το database και το table αν δεν υπάρχουν ήδη
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

# VIBER SETTINGS
VIBER_TOKEN = "YOUR_VIBER_TOKEN"
MY_VIBER_ID = "YOUR_VIBER_ID"

@app.get("/")
def home():
    return {"message": "HITL Layer is Online!"}

@app.post("/agent-input")
async def receive_from_agent(data: dict):
    """
    Endpoint που δέχεται αιτήματα από AI Agents.
    Παράδειγμα JSON: {"content": "Έγκριση πληρωμής 50€", "urgency": "high"}
    """
    content = data.get("content", "No content provided")
    urgency = data.get("urgency", "normal")

    print(f"Received HITL request: {content} (Urgency: {urgency})")

    # Routing στο Viber API
    viber_url = "https://chatapi.viber.com/pa/send_message"
    headers = {"X-Viber-Auth-Token": VIBER_TOKEN}
    
    payload = {
        "receiver": MY_VIBER_ID,
        "min_api_version": 1,
        "sender": {"name": "HITL Gateway"},
        "type": "text",
        "text": f"🔔 [HITL {urgency.upper()}]: {content}"
    }

    async with httpx.AsyncClient() as client:
        # Το Gateway κάνει το 'Forward to Human' που ζητάει το MVP
        response = await client.post(viber_url, json=payload, headers=headers)
    
    return {
        "gateway_status": "forwarded",
        "viber_status": response.json()
    }

# Endpoint για να λαμβάνουμε την απάντηση από το Viber (Webhook)
@app.post("/viber-webhook")
async def viber_webhook(request: Request):
    viber_data = await request.json()
    print("Received from Viber:", viber_data)
    return {"status": "ok"}
def receive_from_agent(data: dict):
    # Εδώ θα έρχεται η πληροφορία από τον AI Agent
    print(f"Έλαβα δεδομένα: {data}")
    return {"status": "received", "data_content": data}

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1487051436456939620/usdfzS6VGQ2cbGtJsGlP5MblxJdcWiN58QNkGBTwGn6ivn-aIffdXJVrnmVvzbEZ3yrc"

@app.post("/hitl/request")
async def create_hitl_request(task: HITLTask):
    # Αποθήκευση στη βάση για Audit Trail 
    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)
        
        # 3. Routing στο Discord (Multi-channel delivery [cite: 43])
        message = {
            "content": f"🚨 **New HITL Request**\n**Agent:** {task.agent_id}\n**Urgency:** {task.urgency}\n**Context:** {task.context}\n**Task ID:** {task.id}"
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(DISCORD_WEBHOOK_URL, json=message)
            
    return {"status": "queued", "task_id": task.id}


@app.post("/hitl/respond/{task_id}")
async def human_respond(task_id: int, decision: str, feedback: Optional[str] = None):
    """
    Endpoint για την απόκριση του ανθρώπου.
    decision: 'approved' ή 'rejected'
    """
    with Session(engine) as session:
        # 1. Αναζήτηση του Task (State Management)
        task = session.get(HITLTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 2. Ενημέρωση Κατάστασης & Audit Trail
        task.status = decision
        # Αν θέλεις, πρόσθεσε πεδίο feedback στο HITLTask model σου
        session.add(task)
        session.commit()
        session.refresh(task)
        
        print(f"Task {task_id} updated to {decision} by human.")
        
        return {
            "message": f"Task {task_id} is now {decision}",
            "audit_log": f"Updated at {datetime.now()}"
        }
    
