import pandas as pd
import numpy as np
import os

np.random.seed(42)

def generate_synthetic_data():
    dates = pd.date_range(start='2024-01-01', periods=360, freq='D')
    
    # Exactly 30 Products List
    products = [
        'Organic Milk', 'Whole Wheat Bread', 'Dark Chocolate', 'Greek Yogurt', 'Avocado',
        'Basmati Rice', 'Olive Oil', 'Green Tea', 'Almonds', 'Oat Oatmeal',
        'Peanut Butter', 'Honey', 'Apple Juice', 'Cheddar Cheese', 'Fresh Tomatoes',
        'Chicken Breast', 'Eggs (12 Pack)', 'Pasta Spaghetti', 'Orange Juice', 'Coffee Beans',
        'Dark Roasted Coffee', 'Frozen Berries', 'Granola Bars', 'Protein Powder', 'Soy Milk',
        'Almond Milk', 'Brown Rice', 'Sunflower Oil', 'Black Tea', 'Cashews'
    ]

    all_data = []

    for product in products:
        base_price = np.random.uniform(10, 120)
        for date in dates:
            price = round(base_price + np.random.normal(0, 2), 2)
            quantity = int(max(5, 120 - (price * 0.7) + np.random.normal(0, 8)))
            promo = 1 if np.random.rand() > 0.8 else 0
            if promo:
                price = round(price * 0.85, 2)
                
            all_data.append({
                'Date': date,
                'Product_Name': product,
                'Price': price,
                'Quantity': quantity,
                'Promo': promo
            })

    df = pd.DataFrame(all_data)
    os.makedirs('data', exist_ok=True)
    df.to_csv('data/sales.csv', index=False)
    print(f"✅ Generated sales data for {len(products)} products successfully!")

if __name__ == '__main__':
    generate_synthetic_data()