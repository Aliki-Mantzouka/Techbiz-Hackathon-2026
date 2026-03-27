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

@app.get("/")
def home():
    return {"message": "Το HITL Layer είναι online!"}

@app.post("/agent-input")
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