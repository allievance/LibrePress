from dotenv import load_dotenv
import os
load_dotenv()
import requests

LULU_CLIENT_KEY = os.getenv('LULU_CLIENT_KEY')
LULU_CLIENT_SECRET = os.getenv('LULU_CLIENT_SECRET')

LULU_API_BASE = 'https://api.lulu.com'

def get_lulu_token():
    response = requests.post(
        'https://api.lulu.com/auth/realms/glasstree/protocol/openid-connect/token',
        data={
            'grant_type': 'client_credentials',
            'client_id': LULU_CLIENT_KEY,
            'client_secret': LULU_CLIENT_SECRET,
        }
    )
    print("Lulu auth response:", response.status_code, response.text)
    return response.json()['access_token']

def create_print_job(order_data):
    token = get_lulu_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(
        f'{LULU_API_BASE}/print-jobs/',
        json=order_data,
        headers=headers
    )
    print("Lulu print job response:", response.status_code, response.text)
    if response.status_code == 201:
        return response.json()
    else:
        print("Lulu error:", response.status_code, response.text)
    return None