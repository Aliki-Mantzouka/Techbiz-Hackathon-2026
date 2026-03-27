from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Το HITL Layer είναι online!"}

@app.post("/agent-input")
def receive_from_agent(data: dict):
    # Εδώ θα έρχεται η πληροφορία από τον AI Agent
    print(f"Έλαβα δεδομένα: {data}")
    return {"status": "received", "data_content": data}