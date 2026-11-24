import requests
import json

# Test the analyze endpoint
url = "http://127.0.0.1:5000/analyze"
data = {"price": 120, "price_lag": 115}

print(f"Sending request to {url}...")
try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success! Response Data:")
        print(json.dumps(response.json(), indent=4))
    else:
        print(f"Error: Server returned status {response.status_code}")
        print(response.text)
except Exception as e:
    print("Backend is unreachable. Is app.py running in another terminal?")
    print(f"Error Details: {e}") 