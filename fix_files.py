import os
import shutil

def fix_files():
    # Absolute path check for your external drive
    base_dir = "data" 
    archive_dir = os.path.join(base_dir, "archive")

    # 1. Move files if archive exists and has files
    if os.path.exists(archive_dir):
        for filename in os.listdir(archive_dir):
            src_path = os.path.join(archive_dir, filename)
            if os.path.isfile(src_path):
                dst_path = os.path.join(base_dir, filename)
                shutil.move(src_path, dst_path)
                print(f"Moved {filename} to data folder.")

    # 2. Precise Renaming Logic
    for filename in os.listdir(base_dir):
        src_path = os.path.join(base_dir, filename)
        if not os.path.isfile(src_path): continue
        
        new_name = filename
        lower_name = filename.lower()
        
        # Standardizing names for prepare_kaggle_data.py
        if "onlineretail" in lower_name or "online retail" in lower_name:
            new_name = "Online Retail.csv"
        elif "order_items" in lower_name:
            new_name = "olist_order_items_dataset.csv"
        elif "orders_dataset" in lower_name:
            new_name = "olist_orders_dataset.csv"
        elif "products_dataset" in lower_name:
            new_name = "olist_products_dataset.csv"
        elif "translation" in lower_name:
            new_name = "product_category_name_translation.csv"
        
        if new_name != filename:
            dst_path = os.path.join(base_dir, new_name)
            if os.path.exists(dst_path): os.remove(dst_path) # Clean old file if exists
            os.rename(src_path, dst_path)
            print(f"✅ Corrected Name: {filename} -> {new_name}")

    print("🚀 Data Reorganization complete.")

if __name__ == "__main__":
    fix_files() 
