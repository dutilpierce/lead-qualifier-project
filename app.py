import os
import requests
import sqlite3
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

# 1. INITIALIZATION
app = Flask(__name__)
client = OpenAI(api_key="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")

# 2. CONFIGURATION - Your Make.com URL
MAKE_WEBHOOK_URL = "https://hook.us2.make.com/txc3a9vxbm4rseba40i69s9vik532inw"

# 3. DASHBOARD PUSH FUNCTION
def send_lead_to_dashboard(project_type, budget, location):
    """Sends qualified lead data to Make.com -> Google Sheets -> Your Website"""
    payload = {
        "timestamp": datetime.now().strftime("%m/%d/%Y %H:%M"),
        "project_type": project_type,
        "budget": budget,
        "location": location,
        "status": "Qualified ✅"
    }
    try:
        # Sends data to the webhook you just set up in Make.com
        response = requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=5)
        print(f"📊 Dashboard Sync Status: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Dashboard Sync Error: {e}")

# 4. DATABASE HELPER
def save_lead(phone, log):
    conn = sqlite3.connect('lead_qualifier.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO leads (phone_number, chat_log) VALUES (?, ?)", (phone, log))
    conn.commit()
    conn.close()

# 5. MAIN BOT LOGIC
@app.route("/sms", methods=['POST'])
def sms_reply():
    phone_number = request.form.get('From')
    incoming_msg = request.form.get('Body')

    # Retrieve or start chat history
    conn = sqlite3.connect('lead_qualifier.db')
    c = conn.cursor()
    c.execute("SELECT chat_log FROM leads WHERE phone_number = ?", (phone_number,))
    row = c.fetchone()
    chat_history = row[0] if row else "System: You are Siftly AI, a professional lead qualifier for contractors. Ask for Project Type, Budget, and Location."
    conn.close()

    # Append user message and get AI response
    new_history = f"{chat_history}\nUser: {incoming_msg}"
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": new_history}]
    )
    
    ai_msg = response.choices[0].message.content
    final_history = f"{new_history}\nAI: {ai_msg}"

    # 6. AUTOMATIC QUALIFICATION CHECK
    # This checks if the AI has gathered all info and "Qualified" the lead
    if "QUALIFIED" in ai_msg.upper():
        # In a real scenario, you'd use AI to extract these specific variables.
        # For now, we pass the logic to your dashboard sync:
        send_lead_to_dashboard("New Lead", "TBD", "Pending")
        
    save_lead(phone_number, final_history)

    resp = MessagingResponse()
    resp.message(ai_msg)
    return str(resp)

if __name__ == "__main__":
    app.run(port=5000)