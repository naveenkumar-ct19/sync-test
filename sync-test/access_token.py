import requests
import time
import os 
from dotenv import load_dotenv,set_key 
import requests, json 
import base64
load_dotenv()


def get_access_token():
    print("Getting Access Token")
    url = "https://id.cisco.com/oauth2/default/v1/token"
    payload = "grant_type=client_credentials" 
    value = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode('utf-8')).decode('utf-8') 
    headers = { "Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Basic {value}" }
    token_response = requests.request("POST", url, headers=headers, data=payload) 
    token_data = token_response.json()
    api_key = token_data.get('access_token')
    return api_key

def main(index_cur):
    global CLIENT_ID
    global CLIENT_SECRET
    global TOKEN_URL
    global APP_KEY
    index_curr=index_cur
    CLIENT_ID = os.getenv(f"CISCO_LLM_CLIENT_ID_{index_curr}")
    CLIENT_SECRET = os.getenv(f"CISCO_LLM_CLIENT_SECRET_{index_curr}")
    TOKEN_URL = os.getenv(f"CISCO_LLM_TOKEN_URL_{index_curr}")
    APP_KEY = os.getenv(f"CISCO_OPENAI_APP_KEY_{index_curr}")
    env_path = ".env"
    api_key = get_access_token()  # Replace with your actual token
    print(api_key[-10:])
    # Update or add ACCESS_TOKEN in the .env file
    set_key(env_path, f"ACCESS_TOKEN", api_key)
    print(f"Setting the app_key as {APP_KEY}")
    set_key(env_path, f"CISCO_OPENAI_APP_KEY", APP_KEY)

    # Reload environment variables to reflect the change immediately
    load_dotenv(env_path, override=True)

    # Now you can access ACCESS_TOKEN via os.getenv
    print("Done" if os.getenv(f"ACCESS_TOKEN") else "failed to get access token")

if __name__ == "__main__":
    main(1)
