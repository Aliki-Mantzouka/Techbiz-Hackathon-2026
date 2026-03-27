import smtplib
from email.mime.text import MIMEText

# ΡΥΘΜΙΣΕΙΣ ΓΙΑ ΤΟ EMAIL
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "insert your email"
SENDER_PASSWORD = "16-digit code"

async def send_approval_email(agent_id: str, context: str, task_id: int, receiver_email: str):
    """
    Στέλνει email για χειροκίνητη έγκριση μέσω Swagger.
    Επιστρέφει True αν σταλεί επιτυχώς, False αν αποτύχει.
    """
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
        # Σύνδεση και αποστολή
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Ασφαλής σύνδεση
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
            print(f"✅ Email sent successfully to {receiver_email}")
            return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False