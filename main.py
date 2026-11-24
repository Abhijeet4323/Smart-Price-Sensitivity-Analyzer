import requests

# Test the analyze endpoint
url = "http://127.0.0.1:5000/analyze"
data = {"price": 120}

try:
    response = requests.post(url, json=data)
    print("Status Code:", response.status_code)
    print("Response Data:", response.json())
except Exception as e:
    print("Backend is unreachable:", e) 