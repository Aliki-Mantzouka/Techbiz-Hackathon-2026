from datetime import datetime
from fastapi import FastAPI, HTTPException
from sqlmodel import Session, SQLModel
from pydantic import BaseModel
import httpx
import smtplib
from email.mime.text import MIMEText
from typing import Optional

# --- ΕΙΣΑΓΩΓΗ ΑΠΟ ΤΑ ΔΙΚΑ ΣΟΥ ΑΡΧΕΙΑ ---
from ntfy import broadcast_to_ntfy
from database import engine, HITLTask

app = FastAPI(title="Multi-Channel HITL Gateway")

# --- ΡΥΘΜΙΣΕΙΣ EMAIL ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "insert your email"
SENDER_PASSWORD = "16-digit code"

# Δημιουργία πινάκων στην εκκίνηση
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

# Μοντέλο για το Swagger
class NotificationInput(BaseModel):
    agent_id: str
    context: str
    urgency: str

# ΡΥΘΜΙΣΕΙΣ DISCORD
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1487051436456939620/usdfzS6VGQ2cbGtJsGlP5MblxJdcWiN58QNkGBTwGn6ivn-aIffdXJVrnmVvzbEZ3yrc"

# --- ΣΥΝΑΡΤΗΣΗ ΑΠΟΣΤΟΛΗΣ EMAIL ---
async def send_approval_email(agent_id: str, context: str, task_id: int, receiver_email: str):
    subject = f"🚨 HITL Action Required (ID: {task_id})"
    body = f"""
    Γεια σου,
    Υπάρχει ένα νέο αίτημα που απαιτεί την έγκρισή σου:
    --------------------------------------
    ID Εργασίας: {task_id}
    Agent: {agent_id}
    Περιεχόμενο: {context}
    --------------------------------------
    """
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = receiver_email
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
            print(f"✅ Email sent to {receiver_email}")
            return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False

# --- 1. DISCORD SECTION ---
@app.post("/discord/send", tags=["Discord"])
async def send_to_discord(data: NotificationInput):
    with Session(engine) as session:
        new_task = HITLTask(agent_id=data.agent_id, context=data.context, urgency=data.urgency)
        session.add(new_task)
        session.commit()
        session.refresh(new_task)
        msg_content = f"👾 **Discord Alert**\n**Agent:** {new_task.agent_id}\n**Context:** {new_task.context}\n**Task ID:** {new_task.id}"
    
    async with httpx.AsyncClient() as client:
        await client.post(DISCORD_WEBHOOK_URL, json={"content": msg_content})
    return {"status": "Sent to Discord", "task_id": new_task.id}

# --- 2. NTFY (MOBILE) SECTION ---
@app.post("/ntfy/send", tags=["NTFY (Mobile)"])
async def send_to_ntfy(data: NotificationInput):
    with Session(engine) as session:
        new_task = HITLTask(agent_id=data.agent_id, context=data.context, urgency=data.urgency)
        session.add(new_task)
        session.commit()
        session.refresh(new_task)

    await broadcast_to_ntfy(new_task.agent_id, new_task.context, new_task.id)
    return {"status": "Sent to Mobile", "task_id": new_task.id}

# --- 3. EMAIL SECTION ---
@app.post("/email/send", tags=["Email"])
async def send_to_email(data: NotificationInput, target_email: str):
    with Session(engine) as session:
        new_task = HITLTask(agent_id=data.agent_id, context=data.context, urgency=data.urgency)
        session.add(new_task)
        session.commit()
        session.refresh(new_task)

    success = await send_approval_email(new_task.agent_id, new_task.context, new_task.id, target_email)
    
    if not success:
        # Αν αποτύχει, στείλε σφάλμα 500
        raise HTTPException(status_code=500, detail="Failed to send email. Check server logs.")
    
    return {"status": "Email Sent Successfully", "task_id": new_task.id}

# --- 4. MANAGEMENT SECTION ---
@app.post("/hitl/respond/{task_id}", tags=["Management"])
async def human_respond(task_id: int, decision: str):
    with Session(engine) as session:
        task = session.get(HITLTask, task_id)
        if not task: 
            raise HTTPException(status_code=404, detail="Task not found")
        
        task.status = decision
        session.add(task)
        session.commit()
        session.refresh(task)

        # Έλεγχος για callback αν υπάρχει στο μοντέλο σου
        if hasattr(task, 'callback_url') and task.callback_url:
            async with httpx.AsyncClient() as client:
                try:
                    await client.post(task.callback_url, json={"task_id": task_id, "decision": decision})
                except Exception as e:
                    print(f"Callback failed: {e}")
        
        return {"message": f"Task {task_id} status updated to {decision}", "status": task.status}

# Ενσωμάτωση εξωτερικού router
try:
    from hitl_engine import router as hitl_router
    app.include_router(hitl_router)
except ImportError:
    print("hitl_engine.py not found, skipping router inclusion.")