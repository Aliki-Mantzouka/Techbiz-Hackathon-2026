import httpx

# ΡΥΘΜΙΣΕΙΣ ΓΙΑ ΤΟ NTFY
# Εδώ ορίζεις ποιοι θα λαμβάνουν τα μηνύματα
NTFY_TOPICS = ["eva04", "nodashackathon"]

async def broadcast_to_ntfy(agent_id: str, context: str):
    """
    Συνάρτηση για την αποστολή ειδοποιήσεων σε πολλαπλά ntfy topics.
    """
    # Φτιάχνουμε το κείμενο του μηνύματος
    msg_text = f"📱 [Mobile Alert] {agent_id}: {context}"
    
    async with httpx.AsyncClient() as client:
        for topic in NTFY_TOPICS:
            try:
                # Αποστολή στο ntfy.sh
                res = await client.post(
                    f"https://ntfy.sh/{topic}", 
                    data=msg_text.encode('utf-8')
                )
                
                if res.status_code == 200:
                    print(f"✅ Notification sent to topic: {topic}")
                else:
                    print(f"⚠️ Failed to send to {topic}. Status: {res.status_code}")
                    
            except Exception as e:
                print(f"❌ Error broadcasting to {topic}: {str(e)}")

    return True