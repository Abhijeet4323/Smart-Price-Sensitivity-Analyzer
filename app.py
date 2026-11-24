
from flask import Flask, render_template, request, jsonify, Response
import pandas as pd
import numpy as np
import io
import os
import requests
import sqlite3
import json
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

from src.model import PriceAnalyzer
from src.visualization import generate_enterprise_visualizations

load_dotenv()

app = Flask(__name__)
analyzers = {}
product_list = []

UPSCRAPE_API_KEY = os.getenv("UPSCRAPE_API_KEY")
DB_PATH = "data/price_history.db"


# ---------------- PRICE HISTORY DATABASE ----------------

def init_price_database():
    os.makedirs("data", exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_key TEXT NOT NULL,
                product_name TEXT,
                marketplace TEXT,
                url TEXT,
                price_value REAL,
                mrp_value REAL,
                checked_at TEXT NOT NULL
            )
        """)
        conn.commit()


def save_price_snapshot(
    product_key, product_name, marketplace,
    url, price_value, mrp_value=None
):
    try:
        price_value = float(price_value)
        if not np.isfinite(price_value) or price_value <= 0:
            return
    except (TypeError, ValueError):
        return

    try:
        mrp_value = (
            float(mrp_value)
            if mrp_value not in (None, "")
            else None
        )
        if mrp_value is not None and (
            not np.isfinite(mrp_value) or mrp_value <= 0
        ):
            mrp_value = None
    except (TypeError, ValueError):
        mrp_value = None

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO price_history
            (product_key, product_name, marketplace, url,
             price_value, mrp_value, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(product_key), str(product_name), marketplace,
            url, price_value, mrp_value,
            datetime.now().isoformat(timespec="seconds")
        ))
        conn.commit()


def get_price_history(product_key):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT price_value, mrp_value, checked_at
            FROM price_history
            WHERE product_key = ?
            ORDER BY checked_at ASC
        """, (str(product_key),)).fetchall()

    return [
        {
            "price_value": row[0],
            "mrp_value": row[1],
            "date": row[2],
            "checked_at": row[2]
        }
        for row in rows
    ]


# ---------------- FUTURE PRICE ESTIMATION ----------------

def predict_future_price(history):
    by_day = {}

    for item in history or []:
        try:
            price = float(item.get("price_value"))
            date_text = str(
                item.get("date") or item.get("checked_at") or ""
            )

            if (
                price <= 0
                or not np.isfinite(price)
                or not date_text
            ):
                continue

            parsed_date = pd.to_datetime(
                date_text, errors="coerce"
            )

            if pd.isna(parsed_date):
                continue

            day = parsed_date.strftime("%Y-%m-%d")

            if (
                day not in by_day
                or date_text >= by_day[day]["date"]
            ):
                by_day[day] = {
                    "price": price,
                    "date": date_text
                }

        except (TypeError, ValueError):
            continue

    observations = [
        by_day[day] for day in sorted(by_day)
    ]

    prices = np.array(
        [item["price"] for item in observations],
        dtype=float
    )

    count = len(prices)

    if count == 0:
        return {
            "direction": "No price history available",
            "next_7_days": None,
            "next_1_month": None,
            "next_2_months": None,
            "buying_range": None,
            "buying_advice": (
                "Track the product to collect its current price."
            ),
            "confidence": "No valid observations",
            "observations": 0
        }

    current = float(prices[-1])

    if count < 3:
        spread = max(current * 0.03, 1.0)

        low = round(max(0.0, current - spread), 2)
        high = round(current + spread, 2)

        def rough_range():
            return {
                "min": low,
                "max": high
            }

        return {
            "direction": "Not enough data to determine trend",
            "next_7_days": rough_range(),
            "next_1_month": rough_range(),
            "next_2_months": rough_range(),
            "buying_range": (
                f"₹{low:,.0f} – ₹{high:,.0f}"
            ),
            "buying_advice": (
                "Low-confidence reference only. Track prices on "
                "at least 3 different dates for a basic trend estimate."
            ),
            "confidence": (
                f"Low confidence ({count}/3 different dates)"
            ),
            "observations": count
        }

    x = np.arange(count, dtype=float)

    slope = float(np.polyfit(x, prices, 1)[0])
    recent = prices[-min(10, count):]
    volatility = float(np.std(recent))

    def make_range(days):
        center = max(0.0, current + slope * days)

        spread = max(
            current * 0.03,
            volatility * 1.25,
            1.0
        )

        return {
            "min": round(max(0.0, center - spread), 2),
            "max": round(center + spread, 2)
        }

    if slope < -0.05:
        direction = "Likely to decrease"
    elif slope > 0.05:
        direction = "Likely to increase"
    else:
        direction = "Likely to remain stable"

    buy_low = float(np.percentile(recent, 20))
    buy_high = float(np.percentile(recent, 45))

    buying_range = (
        f"₹{buy_low:,.0f} – ₹{buy_high:,.0f}"
    )

    if current <= buy_high:
        advice = (
            "Current price is within the recent favourable zone."
        )
    elif slope < 0:
        advice = (
            "Recent trend is downward. Keep tracking if the "
            "purchase is not urgent."
        )
    else:
        advice = (
            "Current price is above the recent favourable zone."
        )

    return {
        "direction": direction,
        "next_7_days": make_range(7),
        "next_1_month": make_range(30),
        "next_2_months": make_range(60),
        "buying_range": buying_range,
        "buying_advice": advice,
        "confidence": (
            "Basic estimate based on tracked observations; "
            "not a guaranteed future price."
        ),
        "observations": count
    }


# ---------------- UP SCRAPE RESPONSE HELPERS ----------------

def parse_api_response(value):
    """
    Upscrape response mein nested dictionaries, lists
    aur JSON-string values ko normalise karta hai.
    """
    if isinstance(value, str):
        text = value.strip()

        if text.startswith("{") or text.startswith("["):
            try:
                return parse_api_response(json.loads(text))
            except (ValueError, TypeError):
                return value

        return value

    if isinstance(value, dict):
        return {
            key: parse_api_response(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            parse_api_response(item)
            for item in value
        ]

    return value


def walk_api_data(value):
    """Nested response ke sabhi dictionaries ko search karta hai."""
    if isinstance(value, dict):
        yield value

        for item in value.values():
            yield from walk_api_data(item)

    elif isinstance(value, list):
        for item in value:
            yield from walk_api_data(item)


def to_number(value):
    """₹14,446, INR 14446 aur numeric values ko number mein badalta hai."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        number = float(value)
        return number if np.isfinite(number) else None

    if isinstance(value, dict):
        for key in ("amount", "value", "price", "current_value"):
            if key in value:
                number = to_number(value[key])
                if number is not None:
                    return number
        return None

    text = str(value).strip()

    if not text:
        return None

    text = (
        text.replace("₹", "")
        .replace("INR", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace(",", "")
        .strip()
    )

    # Price text mein se numeric amount nikalna.
    match = re.search(r"\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        number = float(match.group())

        if not np.isfinite(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


def find_api_value(data, possible_keys):
    """
    Nested response mein diye gaye keys ko priority order mein
    search karta hai.
    """
    dictionaries = list(walk_api_data(data))

    for key in possible_keys:
        for item in dictionaries:
            if key in item:
                value = item[key]

                if value not in (None, ""):
                    return value

    return None


def find_api_images(data):
    image = find_api_value(
        data,
        ["image", "image_url", "main_image", "thumbnail"]
    )

    images = find_api_value(
        data,
        ["images", "image_urls", "product_images"]
    )

    if isinstance(images, str):
        images = [images]

    if not isinstance(images, list):
        images = []

    clean_images = []

    for item in images:
        if isinstance(item, str) and item.startswith("http"):
            clean_images.append(item)

        elif isinstance(item, dict):
            image_url = (
                item.get("url")
                or item.get("src")
                or item.get("image_url")
            )

            if isinstance(image_url, str):
                clean_images.append(image_url)

    if isinstance(image, dict):
        image = (
            image.get("url")
            or image.get("src")
            or image.get("image_url")
        )

    if not isinstance(image, str) or not image.startswith("http"):
        image = clean_images[0] if clean_images else None

    if image and image not in clean_images:
        clean_images.insert(0, image)

    return image, clean_images


# ---------------- LOAD SALES DATA AND TRAIN MODELS ----------------

def initialize_system():
    global product_list, analyzers

    raw_df = pd.read_csv("data/sales.csv")

    column_mapping = {
        "Date": "transaction_date",
        "Price": "unit_price",
        "Quantity": "quantity",
        "Promo": "discount_amount",
        "Product_Name": "product_name",
        "Product": "product_name"
    }

    raw_df.rename(columns=column_mapping, inplace=True)

    if "transaction_date" not in raw_df.columns:
        raise ValueError(
            "sales.csv must contain Date or transaction_date."
        )

    raw_df["transaction_date"] = pd.to_datetime(
        raw_df["transaction_date"], errors="coerce"
    )

    raw_df = raw_df.dropna(
        subset=["transaction_date"]
    ).copy()

    if raw_df.empty:
        raise ValueError(
            "No valid dates found in data/sales.csv."
        )

    if "unit_price" not in raw_df.columns:
        raw_df["unit_price"] = 50.0

    if "quantity" not in raw_df.columns:
        raw_df["quantity"] = 1

    raw_df["unit_price"] = pd.to_numeric(
        raw_df["unit_price"], errors="coerce"
    ).fillna(50)

    raw_df["quantity"] = pd.to_numeric(
        raw_df["quantity"], errors="coerce"
    ).fillna(1)

    raw_df["month"] = raw_df["transaction_date"].dt.month

    raw_df["is_weekend"] = (
        raw_df["transaction_date"].dt.dayofweek >= 5
    ).astype(int)

    if "final_amount" not in raw_df.columns:
        raw_df["final_amount"] = (
            raw_df["unit_price"] * raw_df["quantity"]
        )

    if "discount_amount" in raw_df.columns:
        raw_df["discount_amount"] = pd.to_numeric(
            raw_df["discount_amount"], errors="coerce"
        ).fillna(0)

        raw_df["promo"] = (
            raw_df["discount_amount"] > 0
        ).astype(int)
    else:
        raw_df["promo"] = 0

    if "product_name" not in raw_df.columns:
        raw_df["product_name"] = "Default Product"

    raw_df["product_name"] = (
        raw_df["product_name"]
        .fillna("Default Product")
        .astype(str)
    )

    product_list = sorted(
        raw_df["product_name"].unique().tolist()
    )

    analyzers.clear()

    for product in product_list:
        product_df = raw_df[
            raw_df["product_name"] == product
        ].copy()

        try:
            model = PriceAnalyzer()
            model.fit(product_df)

            analyzers[product] = {
                "model": model,
                "df": product_df
            }

        except Exception as error:
            print(
                f"Model training failed for {product}: {error}"
            )

    print(f"Loaded {len(analyzers)} products.")


init_price_database()
initialize_system()


# ---------------- DASHBOARD ----------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        products=product_list
    )


# ---------------- PRODUCT ANALYSIS + PROFIT/LOSS ----------------

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(silent=True) or {}

        product_name = data.get("product_name")
        price = float(data.get("price", 50))

        if not np.isfinite(price) or price <= 0:
            return jsonify({
                "success": False,
                "message": "Price must be a positive number."
            }), 400

        ctx = analyzers.get(product_name)

        if ctx is None:
            return jsonify({
                "success": False,
                "message": (
                    "Selected product was not found or its model failed."
                )
            }), 404

        model = ctx["model"]
        product_df = ctx["df"]

        month = float(product_df["month"].mean())
        weekend = float(product_df["is_weekend"].mean())

        demand = max(
            0,
            int(model.predict_demand(price, month, weekend))
        )

        revenue = round(price * demand, 2)

        elasticity = round(
            float(model.get_elasticity()), 2
        )

        visualizations = generate_enterprise_visualizations(
            model, product_df, price
        )

        historical_prices = pd.to_numeric(
            product_df["unit_price"], errors="coerce"
        ).dropna()

        average_price = (
            float(historical_prices.mean())
            if not historical_prices.empty
            else price
        )

        if (
            not np.isfinite(average_price)
            or average_price <= 0
        ):
            average_price = price

        estimated_cost = round(
            average_price * 0.70, 2
        )

        profit_loss = round(
            (price - estimated_cost) * demand, 2
        )

        if profit_loss > 0:
            profit_status = "Profit"
        elif profit_loss < 0:
            profit_status = "Loss"
        else:
            profit_status = "Break-even"

        curve_prices = np.linspace(
            max(1.0, price * 0.25),
            max(price * 2.0, price + 1),
            25
        )

        curve_profit = []

        for curve_price in curve_prices:
            try:
                curve_demand = max(
                    0,
                    float(
                        model.predict_demand(
                            float(curve_price),
                            month,
                            weekend
                        )
                    )
                )

                curve_profit.append(
                    round(
                        (
                            float(curve_price)
                            - estimated_cost
                        ) * curve_demand,
                        2
                    )
                )

            except Exception:
                curve_profit.append(0.0)

        optimal_price = (
            visualizations.get("opt_price")
            if isinstance(visualizations, dict)
            else None
        )

        if optimal_price is None:
            optimal_price = price

        return jsonify({
            "success": True,
            "price": price,
            "simulated_price": price,
            "demand": demand,
            "revenue": revenue,
            "elasticity": elasticity,
            "graphs": visualizations,
            "opt_p": f"{float(optimal_price):.1f}",
            "estimated_cost": estimated_cost,
            "profit_loss": profit_loss,
            "profit_status": profit_status,
            "profit_basis": (
                "Estimated unit cost is 70% of average historical "
                "selling price. This is an estimate, not actual "
                "accounting profit."
            ),
            "profit_curve": {
                "prices": [
                    round(float(value), 2)
                    for value in curve_prices
                ],
                "profit": curve_profit
            }
        })

    except Exception as error:
        app.logger.exception("Analysis failed")

        return jsonify({
            "success": False,
            "message": str(error)
        }), 500


# ---------------- CSV EXPORT ----------------

@app.route("/export", methods=["GET"])
def export_report():
    try:
        product_name = request.args.get("product_name")
        price = float(request.args.get("price", 50))

        if not np.isfinite(price) or price <= 0:
            return Response(
                "Price must be a positive number.",
                status=400,
                mimetype="text/plain"
            )

        ctx = analyzers.get(product_name)

        if ctx is None:
            return Response(
                "Product not found.",
                status=404,
                mimetype="text/plain"
            )

        model = ctx["model"]
        product_df = ctx["df"]

        month = float(product_df["month"].mean())
        weekend = float(product_df["is_weekend"].mean())

        demand = max(
            0,
            int(model.predict_demand(price, month, weekend))
        )

        revenue = round(price * demand, 2)

        average_price = float(
            product_df["unit_price"].mean()
        )

        estimated_cost = average_price * 0.70

        profit_loss = (
            price - estimated_cost
        ) * demand

        report_df = pd.DataFrame({
            "Metric": [
                "Product Name",
                "Simulated Price (INR)",
                "Predicted Demand",
                "Projected Revenue (INR)",
                "Estimated Unit Cost (INR)",
                "Estimated Profit/Loss (INR)"
            ],
            "Value": [
                product_name,
                price,
                demand,
                revenue,
                round(estimated_cost, 2),
                round(profit_loss, 2)
            ]
        })

        output = io.StringIO()
        report_df.to_csv(output, index=False)

        safe_name = (
            str(product_name)
            .replace("/", "_")
            .replace("\\", "_")
        )

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition":
                    f"attachment; filename={safe_name}_Price_Report.csv"
            }
        )

    except Exception as error:
        app.logger.exception("CSV export failed")

        return Response(
            f"Export error: {error}",
            status=500,
            mimetype="text/plain"
        )


# ---------------- FLIPKART PRICE TRACKER ----------------

@app.route("/product-price", methods=["POST"])
def product_price():
    try:
        data = request.get_json(silent=True) or {}
        product_url = str(data.get("url", "")).strip()

        if not product_url:
            return jsonify({
                "success": False,
                "message": "Please enter a product URL."
            }), 400

        parsed = urlparse(product_url)

        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return jsonify({
                "success": False,
                "message": "Enter a valid complete product URL."
            }), 400

        hostname = parsed.netloc.lower().split("@")[-1].split(":")[0]

        if hostname.startswith("www."):
            hostname = hostname[4:]

        if not (
            hostname == "flipkart.com"
            or hostname.endswith(".flipkart.com")
        ):
            return jsonify({
                "success": False,
                "message": "Current live price integration supports Flipkart only."
            }), 400

        if not UPSCRAPE_API_KEY:
            return jsonify({
                "success": False,
                "message": "UPSCRAPE_API_KEY was not found in .env."
            }), 500

        # Upscrape API request
        response = requests.post(
            "https://data.upscrape.com/execute",
            headers={
                "Authorization": f"Bearer {UPSCRAPE_API_KEY}",
                "Content-Type": "application/json",
                "Prefer": "wait=30"
            },
            json={
                "capability": "flipkart.product.get",
                "input": {
                    "url": product_url
                },
                "max_credits": 2
            },
            timeout=60
        )

        app.logger.info(
            "UPSCRAPE API STATUS: %s",
            response.status_code
        )

        if response.status_code != 200:
            app.logger.error(
                "UPSCRAPE API ERROR: %s",
                response.text[:1500]
            )

            return jsonify({
                "success": False,
                "message": "Flipkart price API returned an error.",
                "api_status": response.status_code,
                "details": response.text[:1000]
            }), 502

        try:
            result = response.json()
        except ValueError:
            app.logger.error(
                "Upscrape returned non-JSON response: %s",
                response.text[:1000]
            )

            return jsonify({
                "success": False,
                "message": "Upscrape returned an invalid JSON response."
            }), 502

        result = parse_api_response(result)

        if not isinstance(result, (dict, list)):
            return jsonify({
                "success": False,
                "message": "Unexpected response received from Upscrape."
            }), 502

        app.logger.info(
            "UPSCRAPE RESPONSE KEYS: %s",
            list(result.keys()) if isinstance(result, dict) else "List response"
        )

        # Product name
        product_name = find_api_value(
            result,
            [
                "title",
                "product_title",
                "product_name",
                "name"
            ]
        )

        if isinstance(product_name, dict):
            product_name = (
                product_name.get("text")
                or product_name.get("value")
            )

        if not isinstance(product_name, str) or not product_name.strip():
            product_name = "Flipkart Product"

        # Price fields: offer price is preferred.
        raw_price = find_api_value(
            result,
            [
                "price_with_best_offer",
                "selling_price",
                "special_price",
                "current_price",
                "sale_price",
                "price_value",
                "price"
            ]
        )

        # MRP fields
        raw_mrp = find_api_value(
            result,
            [
                "mrp",
                "maximum_retail_price",
                "original_price",
                "regular_price",
                "list_price"
            ]
        )

        # Discount
        discount = find_api_value(
            result,
            [
                "discount_percent",
                "discount_percentage",
                "discount"
            ]
        )

        price_value = to_number(raw_price)
        mrp_value = to_number(raw_mrp)

        # If primary price field is a wrapper or unavailable,
        # try additional price fields individually.
        if price_value is None or price_value <= 0:
            fallback_keys = [
                "selling_price",
                "special_price",
                "current_price",
                "sale_price",
                "price_value",
                "price",
                "price_with_best_offer"
            ]

            for key in fallback_keys:
                candidate = find_api_value(result, [key])
                candidate_number = to_number(candidate)

                if (
                    candidate_number is not None
                    and candidate_number > 0
                ):
                    price_value = candidate_number
                    break

        if price_value is None or price_value <= 0:
            app.logger.error(
                "Could not find price in Upscrape response."
            )

            return jsonify({
                "success": False,
                "message": (
                    "API response did not contain a valid product price."
                ),
                "details": (
                    "Upscrape response structure could not be matched. "
                    "Check the Flask terminal output for response details."
                )
            }), 502

        # Product ID from API, or Flipkart URL PID as fallback.
        product_key = find_api_value(
            result,
            [
                "product_id",
                "pid",
                "listing_id",
                "sku"
            ]
        )

        if isinstance(product_key, dict):
            product_key = (
                product_key.get("value")
                or product_key.get("id")
            )

        if not product_key:
            query_params = parse_qs(parsed.query)
            pid_values = query_params.get("pid", [])

            if pid_values:
                product_key = pid_values[0]
            else:
                product_key = product_url

        # Product images
        image, images = find_api_images(result)

        # Discount conversion
        discount_value = to_number(discount)

        if (
            discount_value is None
            and mrp_value
            and mrp_value > price_value
        ):
            discount_value = round(
                (mrp_value - price_value) / mrp_value * 100,
                1
            )

        # Save price in SQLite
        save_price_snapshot(
            str(product_key),
            str(product_name),
            "Flipkart",
            product_url,
            price_value,
            mrp_value
        )

        # Retrieve price history
        history = get_price_history(str(product_key))

        # Future price estimation
        prediction = predict_future_price(history)

        return jsonify({
            "success": True,
            "marketplace": "Flipkart",
            "product_url": product_url,
            "product_name": product_name,
            "current_price": price_value,
            "price_value": price_value,
            "mrp": mrp_value,
            "discount_percent": discount_value,
            "product_image": image,
            "images": images,
            "price_history": history,
            "prediction": prediction,
            "message": "Product price fetched and saved successfully."
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "success": False,
            "message": "Price API timed out. Please try again."
        }), 504

    except requests.exceptions.RequestException as error:
        app.logger.exception("Price API connection failed")

        return jsonify({
            "success": False,
            "message": str(error)
        }), 502

    except Exception as error:
        app.logger.exception("Price tracking failed")

        return jsonify({
            "success": False,
            "message": str(error)
        }), 500


# ---------------- RUN FLASK APP ----------------

if __name__ == "__main__":
    app.run(debug=True, port=5001)
