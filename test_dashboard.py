import requests
import json
from datetime import datetime

# 1. YOUR CONFIGURATION
# Replace this with the URL you copied from the Make.com Webhook module
MAKE_WEBHOOK_URL = "https://hook.us2.make.com/txc3a9vxbm4rseba40i69s9vik532inw"

def send_test_lead(project, budget, location):
    print(f"🚀 Sending test lead to Siftly Dashboard: {project}...")
    
    # Data structure to match your Google Sheet columns
    payload = {
        "timestamp": datetime.now().strftime("%m/%d/%Y %H:%M"),
        "project_type": project,
        "budget": budget,
        "location": location,
        "status": "Qualified ✅"
    }

    try:
        response = requests.post(
            MAKE_WEBHOOK_URL, 
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print("✅ Success! Check your Make.com scenario and Google Sheet.")
        else:
            print(f"❌ Failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"⚠️ Error connecting to Webhook: {e}")

# 2. RUN THE TEST
if __name__ == "__main__":
    # You can change these values to see different rows appear in your sheet
    send_test_lead("Full Backyard Remodel", "$15,000 - $20,000", "Austin, TX")