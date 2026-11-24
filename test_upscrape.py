import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("UPSCRAPE_API_KEY")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Prefer": "wait=30"
}

payload = {
    "capability": "flipkart.product.get",
    "input": {
        "url": "https://www.flipkart.com/timex-tweg33901-signio-round-43mm-coffee-dial-automatic-analog-watch-men/p/itm8cf9be3560e0e?pid=WATHM5G8FWXGYSBH"
    },
    "max_credits": 2
}

response = requests.post(
    "https://data.upscrape.com/execute",
    headers=headers,
    json=payload,
    timeout=60
)

print("STATUS:", response.status_code)
print("RESPONSE:", response.text[:3000])