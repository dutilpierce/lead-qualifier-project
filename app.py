from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
# Ensure scoring_logic.py is in the same folder
# We only import what is strictly needed for qualification
from scoring_logic import calculate_score, FORWARD_TO_CONTRACTOR, DATABASE
import sqlite3
from datetime import datetime

app = Flask(__name__)

# --- DATABASE UTILITY FUNCTIONS ---
# Only includes fields necessary for qualification
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            zip_code TEXT,
            status TEXT NOT NULL,
            qual_score INTEGER,
            project_type TEXT,
            timestamp TEXT
            -- LTV and other fields removed for lean MVP
        )
    """)
    conn.commit()
    conn.close()

def get_lead_status(phone_number):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM leads WHERE phone_number = ?", (phone_number,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'NEW'

def update_lead(phone_number, **kwargs):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    if get_lead_status(phone_number) == 'NEW' and kwargs.get('status') == 'Q1':
        # Insert new lead only on the very first message
        cursor.execute(
            "INSERT INTO leads (phone_number, status, timestamp) VALUES (?, ?, ?)",
            (phone_number, 'Q1', datetime.now().isoformat())
        )
    else:
        # Update existing lead
        set_clause = ', '.join([f'{k} = ?' for k in kwargs.keys()])
        values = list(kwargs.values())
        values.append(phone_number)
        
        cursor.execute(
            f"UPDATE leads SET {set_clause} WHERE phone_number = ?",
            values
        )

    conn.commit()
    conn.close()


# --- QUALIFICATION QUESTIONS ---
QUESTIONS = {
    'Q1': "What is the *ZIP CODE* for the project location? (This is important for scheduling)",
    'Q2': "What is the primary **Project Type**? (A: Emergency Repair, B: Full Replacement, C: Estimate/Inspection)",
    'Q3': "What is your **Timeline** and estimated **Budget**? (E.g., Immediate, $5k-$10k)",
    'Q4': "Thank you! We have enough information to triage your request. We will be in touch shortly."
}


@app.route("/sms", methods=['POST'])
def sms_reply():
    """Handles incoming SMS, reads the conversation state, and sends the next message."""
    
    incoming_msg = request.form.get('Body').strip()
    phone_number = request.form.get('From')

    resp = MessagingResponse()
    current_status = get_lead_status(phone_number)
    
    # 1. TCPA Compliance: Handle STOP/UNSTOP commands
    if incoming_msg.upper() in ['STOP', 'QUIT', 'END']:
        return str(resp) 

    # 2. CONVERSATION FLOW (LEAD SIDE) - Simplified Router
    
    if current_status == 'NEW':
        # Start Q1 logic
        update_lead(phone_number, status='Q1')
        response_text = f"Hi there! This is [Contractor Name] regarding your request. {QUESTIONS['Q1']} Reply STOP to opt-out."
        resp.message(response_text)
        

    elif current_status == 'Q1':
        # Answer to ZIP code received
        update_lead(phone_number, zip_code=incoming_msg, status='Q2')
        resp.message(QUESTIONS['Q2'])

    elif current_status == 'Q2':
        # Answer to Project Type received
        update_lead(phone_number, project_type=incoming_msg, status='Q3')
        resp.message(QUESTIONS['Q3'])

    elif current_status == 'Q3':
        # Answer to Timeline/Budget received - Trigger Scoring
        
        score, classification = calculate_score(phone_number, incoming_msg)
        
        # Update final status/score
        update_lead(phone_number, status=classification, qual_score=score)

        if classification == 'HOT':
            resp.message(f"🚨 HOT LEAD CONFIRMED ({score}/10)! [Contractor Name] is sending a technician immediately. You will get a direct call from them shortly.")
            # Send the alert to the contractor
            FORWARD_TO_CONTRACTOR(phone_number, score)
            
        else: # WARM/COLD
            resp.message(QUESTIONS['Q4']) # Standard closing message
            
    # Handle already qualified leads 
    elif current_status in ['HOT', 'WARM', 'COLD']:
        resp.message("Thanks for the follow-up! We've already logged your info and will be in touch.")

    return str(resp)

if __name__ == '__main__':
    # Initialize the database table when the app starts
    init_db()
    # Run Flask app
    app.run(port=5000, debug=True)

    import requests

# Use the URL you just copied from Make.com
test_url = "https://hook.us2.make.com/txc3a9vxbm4rseba40i69s9vik532inw"

test_data = {
    "timestamp": "2025-12-23",
    "project": "Backyard Fence",
    "budget": "$5,000 - $10,000",
    "status": "Qualified ✅"
}

# Run this once to send the test
requests.post(test_url, json=test_data)