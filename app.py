import os
import requests
import sqlite3
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI
from dotenv import load_dotenv

# 1. INITIALIZATION & SECURITY
# Loads the API key from your hidden .env file
load_dotenv()
app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 2. CONFIGURATION
# Your specific Make.com Webhook URL
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
    conn.close()

    # Initial system prompt instructions
    system_prompt = (
        "You are Siftly AI, a professional lead qualifier for home contractors. "
        "Your goal is to be friendly but efficient. You MUST collect: "
        "1. Project Type, 2. Budget, 3. Location. "
        "Once you have all three, end your message with the exact word: QUALIFIED."
    )

    chat_history = row[0] if row else f"System: {system_prompt}"
    
    # Append user message and get AI response
    messages = [{"role": "system", "content": chat_history}, {"role": "user", "content": incoming_msg}]
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        ai_msg = response.choices[0].message.content
        print(f"🤖 AI says: {ai_msg}")
    except Exception as e:
        print(f"❌ OpenAI Error: {e}")
        ai_msg = "I'm sorry, I'm having a technical glitch. Please try again in a moment."

    # Update history for database
    final_history = f"{chat_history}\nUser: {incoming_msg}\nAI: {ai_msg}"
    save_lead(phone_number, final_history)

    # 6. AUTOMATIC QUALIFICATION CHECK
    if "QUALIFIED" in ai_msg.upper():
        # In a production environment, you would use a second AI call to extract 
        # the specific project/budget/location from the log.
        # For this version, we send the notification that a lead is ready:
        send_lead_to_dashboard("New Siftly Lead", "Check Logs", "See Chat")

    # Twilio Response
    resp = MessagingResponse()
    resp.message(ai_msg)
    return str(resp)

if __name__ == "__main__":
    app.run(port=5000)