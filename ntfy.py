import httpx

NTFY_TOPICS = ["a notify username", "a notify username"]

async def broadcast_to_ntfy(agent_id: str, context: str, task_id: int = None, base_url: str = ""):
    # Το κείμενο του μηνύματος
    msg_text = f"Agent {agent_id} needs approval: {context}"
    
    actions = ""
    if task_id and base_url:
        approve_url = f"{base_url}/hitl-v2/respond/{task_id}?decision=approved"
        reject_url = f"{base_url}/hitl-v2/respond/{task_id}?decision=rejected"
        
        # ΣΗΜΑΝΤΙΚΟ: Το ntfy θέλει "action, label, url" ΧΩΡΙΣ κενά μετά τα κόμματα
        actions = f"view,Approve,{approve_url}; view,Reject,{reject_url}"

    async with httpx.AsyncClient() as client:
        for topic in NTFY_TOPICS:
            headers = {
                "Title": "AI Agent Approval Required",
                "Priority": "high",
                "Tags": "robot",
                "Click": f"{base_url}/hitl-v2/dashboard"  # Αν πατήσουν την ειδοποίηση, πάει στο Dashboard
            }
            if actions:
                headers["Actions"] = actions

            try:
                await client.post(
                    f"https://ntfy.sh/{topic}",
                    data=msg_text.encode('utf-8'),
                    headers={
                        "Title": "New Approval Required",
                        "Priority": "high",
                        "Tags": "envelope"
                    }
                )
            except Exception as e:
                print(f"Error: {e}")
