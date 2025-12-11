import os
from openai import OpenAI
from twilio.rest import Client
import sqlite3

# --- CONFIGURATION (Reads from environment variables set in Step 2.C) ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER")
CONTRACTOR_CELL = os.environ.get("CONTRACTOR_CELL") 

# Safety check for credentials
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_NUMBER, CONTRACTOR_CELL]):
    print("FATAL ERROR: Twilio/Contractor credentials not set in environment variables.")
    # Exit or handle error gracefully in a real production environment

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
DATABASE = 'lead_qualifier.db'


def calculate_score(phone_number, final_answer):
    """
    Uses GPT to extract data, score the lead (0-10), and classify it.
    """
    
    # 1. Retrieve previous conversation data
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT zip_code, project_type FROM leads WHERE phone_number = ?", (phone_number,))
    lead_data = cursor.fetchone()
    conn.close()
    
    if not lead_data:
        return 0, 'COLD'

    zip_code, project_type = lead_data
    
    # 2. System Prompt: Tells the AI how to behave and what rules to use
    system_prompt = f"""
    You are an expert Lead Qualifier for a roofing contractor. Analyze the user's answers 
    and output a JSON object containing a qualification score (0-10) and a HOT/WARM/COLD classification.

    Qualification Rules (Add points for these):
    - Urgency: 'Immediate' or 'Emergency' = +4 points
    - Budget: Mentioning a budget over $5,000 or 'Insurance Claim' = +3 points
    - Project Type: 'Full Replacement' = +2 points
    - Location: If the ZIP code is valid (which it is: {zip_code}) = +1 point

    The user's previous answers: Project Type: {project_type}.
    The user's final answer about timeline/budget: {final_answer}

    Return ONLY a single JSON object with keys "score" (integer) and "classification" (string).
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Final Answers: {final_answer}"}
            ]
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        
        score = int(result.get("score", 0))
        
        if score >= 7:
            classification = 'HOT'
        elif score >= 4:
            classification = 'WARM'
        else:
            classification = 'COLD'
            
        return score, classification
        
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return 0, 'COLD'


def FORWARD_TO_CONTRACTOR(lead_phone, score):
    """Sends the critical alert SMS to the contractor's personal phone."""
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    # Fetch all key data points collected during the conversation
    cursor.execute("SELECT zip_code, project_type FROM leads WHERE phone_number = ?", (lead_phone,))
    lead_data = cursor.fetchone()
    conn.close()

    zip_code, project_type = lead_data
    
    alert_message = (
        f"🚨 URGENT HOT LEAD ({score}/10) 🚨\n"
        f"\n"
        f"CLIENT: {lead_phone}\n"
        f"PROJECT ZIP: {zip_code}\n"
        f"SCOPE: {project_type}\n"
        f"RATING: IMMEDIATE ACTION REQUIRED\n"
        f"\n"
        f"ACTION: CALL NOW and reference Project {zip_code}."
    )
    
    # Send the SMS
    twilio_client.messages.create(
        body=alert_message,
        from_=TWILIO_NUMBER,  # Your Twilio number
        to=CONTRACTOR_CELL     # Contractor's cell number (set in env)
    )