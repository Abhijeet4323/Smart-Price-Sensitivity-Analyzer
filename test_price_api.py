from dotenv import load_dotenv
import os
import requests

load_dotenv()

api_key = os.getenv("DATABLUE_API_KEY")

url = input("Flipkart product URL paste karo: ").strip()

response = requests.post(
    "https://api.datablue.dev/v1/data/flipkart/product",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    },
    json={
        "url": url
    },
    timeout=60
)

print("\nStatus:", response.status_code)
print(response.text)
try:
    data = response.json()

    if data.get("success") and data.get("product"):
        product = data["product"]

        print("\n==============================")
        print("PRODUCT DETAILS")
        print("==============================")
        print("Product:", product.get("title"))
        print("Current Price:", product.get("price"))
        print("Price Value:", product.get("price_value"))
        print("MRP:", product.get("mrp"))
        print("Discount:", product.get("discount_percent"), "%")
        print("==============================")

    else:
        print("\nProduct data nahi mila.")
        print(data)

except ValueError:
    print("\nAPI ne JSON response nahi diya.")
    print(response.text)