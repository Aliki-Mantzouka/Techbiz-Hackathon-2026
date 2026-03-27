from fastapi import FastAPI, Request
import httpx

app = FastAPI()

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