from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, SQLModel, select
from pydantic import BaseModel
import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# Εισαγωγή για το Custom Swagger UI
from fastapi.openapi.docs import get_swagger_ui_html

# --- ΕΙΣΑΓΩΓΗ ΑΠΟ ΤOΠΙΚΑ ΑΡΧΕΙΑ ---
from ntfy import broadcast_to_ntfy
from database import engine, HITLTask
from fastapi.templating import Jinja2Templates
from hitl_engine import get_discord_buttons, BASE_URL

# Ορισμός φακέλου για τα HTML αρχεία
templates = Jinja2Templates(directory="templates")

# Αρχικοποίηση με απενεργοποιημένο το default docs_url
app = FastAPI(
    title="Multi-Channel HITL Gateway", 
    description="A gateway for Human-in-the-Loop requests via Email, Mobile (ntfy), and Discord.", 
    version="1.0",
    docs_url=None, 
    redoc_url=None
)

# --- CUSTOM SWAGGER UI ENDPOINT ---
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - API Docs",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )

# --- ΡΥΘΜΙΣΕΙΣ ---
SENDER_EMAIL = "your email"
SENDER_PASSWORD = "your 16-digit app password"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
DISCORD_WEBHOOK_URL = "your Discord webhook URL"

# Δημιουργία πινάκων στην εκκίνηση
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

# Μοντέλο για το Swagger input
class NotificationInput(BaseModel):
    agent_id: str
    context: str
    urgency: str

# --- ΣΥΝΑΡΤΗΣΗ ΑΠΟΣΤΟΛΗΣ EMAIL ---
async def send_approval_email(agent_id: str, context: str, task_id: int, receiver_email: str, base_url: str):
    subject = f"🚨 HITL Action Required (ID: {task_id})"
    base_url = base_url.rstrip("/")
    
    approve_url = f"{base_url}/hitl-v2/respond/{task_id}?decision=approved"
    reject_url = f"{base_url}/hitl-v2/respond/{task_id}?decision=rejected"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>Νέο Αίτημα Έγκρισης</h2>
        <p>Ο Agent <b>{agent_id}</b> ζητάει έγκριση για το εξής:</p>
        <blockquote style="background: #f4f4f4; padding: 10px; border-left: 5px solid #ccc;">
            {context}
        </blockquote>
        <div style="margin-top: 20px;">
            <a href="{approve_url}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-right: 10px;">✅ APPROVE</a>
            <a href="{reject_url}" style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">❌ REJECT</a>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = receiver_email
    msg.attach(MIMEText(html_body, 'html'))

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

# --- 1. EMAIL SECTION ---
@app.post("/email/send", tags=["📧 Email"])
async def send_to_email(data: NotificationInput, target_email: str):
    with Session(engine) as session:
        new_task = HITLTask(
            agent_id=data.agent_id,
            context=data.context,
            urgency=data.urgency,
            status="pending"
        )
        session.add(new_task)
        session.commit()
        session.refresh(new_task)

    success = await send_approval_email(
        agent_id=new_task.agent_id,
        context=new_task.context,
        task_id=new_task.id,
        receiver_email=target_email,
        base_url=BASE_URL
    )
    
    if success:
        return {"status": "Email sent successfully", "task_id": new_task.id}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email")

# --- 2. NTFY SECTION ---
@app.post("/ntfy/send", tags=["📱 NTFY (Mobile)"])
async def send_to_ntfy_standalone(data: NotificationInput):
    with Session(engine) as session:
        new_task = HITLTask(
            agent_id=data.agent_id,
            context=data.context,
            urgency=data.urgency,
            status="pending"
        )
        session.add(new_task)
        session.commit()
        session.refresh(new_task)

    await broadcast_to_ntfy(
        new_task.agent_id,
        new_task.context,
        task_id=new_task.id,
        base_url=BASE_URL
    )
    
    return {"status": "Sent to Mobile", "task_id": new_task.id}

# --- 3. DISCORD SECTION ---
@app.post("/hitl/request", tags=["💬 HITL Discord"])
async def create_hitl_request(task: HITLTask):
    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)
        
        app_url, rej_url = get_discord_buttons(task.id)
        
        discord_msg = {
            "content": f"🚨 **New HITL Request** (#{task.id})\n"
                       f"**Agent:** `{task.agent_id}`\n"
                       f"**Context:** {task.context}\n\n"
                       f"✅ [APPROVE]({app_url})  |  ❌ [REJECT]({rej_url})"
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(DISCORD_WEBHOOK_URL, json=discord_msg)
            
            if task.urgency.lower() == "high":
                await broadcast_to_ntfy(
                    task.agent_id,
                    task.context,
                    task_id=task.id,
                    base_url=BASE_URL
                )
    return {"status": "dispatched", "task_id": task.id}

# --- 4. DASHBOARD & MANAGEMENT ---
@app.get("/hitl-v2/dashboard", response_class=HTMLResponse, tags=["⚙️ HITL Engine"])
async def get_dashboard(request: Request):
    with Session(engine) as session:
        tasks = session.exec(select(HITLTask)).all()
    return templates.TemplateResponse("index.html", {"request": request, "tasks": tasks})

# Ενσωμάτωση Router από hitl_engine
try:
    from hitl_engine import router as hitl_router
    app.include_router(hitl_router)
except ImportError:
    print("hitl_engine router not found.")
