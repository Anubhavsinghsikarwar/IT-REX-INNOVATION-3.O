import cv2
import pytesseract
import re
import os
from datetime import datetime

# CONFIGURATION
# If on Windows, uncomment the next line and fix the path:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def preprocess_image(image_path):
    """
    Loads full image, upscales, and thresholds for high contrast.
    """
    img = cv2.imread(image_path)
    if img is None: return None

    # 1. Upscale 2x for better text clarity
    processed_img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # 2. Convert to Grayscale
    gray = cv2.cvtColor(processed_img, cv2.COLOR_BGR2GRAY)

    # 3. Threshold (B&W)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return thresh

def clean_price(price, vehicle_type):
    """
    Fixes the 'Rupee symbol read as digit' error.
    e.g., Auto 260 -> 60, Cab 2136 -> 136
    """
    price_str = str(price)
    
    # Rule 1: Bike/Auto shouldn't be > 200 usually. 
    # If it is (e.g. 260, 745) and starts with 2/7, strip the first digit.
    if vehicle_type in ["Bike", "Bike Saver", "Auto"] and price > 200:
        if price_str.startswith(('2', '7', '?')):
            return int(price_str[1:])
            
    # Rule 2: Cabs shouldn't be > 1000 usually for local trips.
    # If it is (e.g. 2136), strip the first digit.
    if price > 1000:
        if price_str.startswith(('2', '7')):
            return int(price_str[1:])
            
    return price

def parse_ride_data(text, app_name):
    results = {}
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        line_lower = line.lower()

        # Regex to find Keyword ... Number
        match = re.search(r'(Bike|Auto|Cab|Uber|Moto).*?(\d{2,5})', line, re.IGNORECASE)
        
        if match:
            raw_keyword = match.group(1).lower()
            raw_price = int(match.group(2))
            service_name = None

            # --- RAPIDO MAPPING ---
            if app_name == "Rapido":
                if "bike" in line_lower: service_name = "Bike"      # Now Included
                elif "auto" in line_lower: service_name = "Auto"
                elif "cab economy" in line_lower: service_name = "Cab Economy"
                elif "cab priority" in line_lower: service_name = "Cab Priority"
                elif "cab" in line_lower: service_name = "Cab Economy"
            
            # --- UBER MAPPING ---
            elif app_name == "Uber":
                if "saver" in line_lower: service_name = "Bike Saver"
                elif "bike" in line_lower: service_name = "Bike"
                elif "auto" in line_lower: service_name = "Auto"    # Now Included
                elif "uber go" in line_lower: service_name = "Cab"
                elif "cab" in line_lower: service_name = "Cab"
                elif "uber" in raw_keyword: service_name = "Cab"

            if service_name:
                # APPLY THE PRICE FIXER
                final_price = clean_price(raw_price, service_name)
                results[service_name] = final_price

    return results

def save_to_file(data_map, filename="ride_data.txt"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"\n--- Update: {timestamp} ---\n")
        for app, items in data_map.items():
            f.write(f"{app}:\n")
            if not items: f.write("  (No Data found)\n")
            for k, v in items.items():
                f.write(f"  {k} = ₹{v}\n")
    print(f"Saved to {filename}")

def main():
    # Update these filenames to match your actual images
    files = {
        "Rapido": "new_device_rapido.png",
        "Uber": "uber_opened.png"
    }
    
    final_data = {}

    for app, path in files.items():
        if os.path.exists(path):
            print(f"Scanning {app}...")
            processed_img = preprocess_image(path)
            if processed_img is not None:
                text = pytesseract.image_to_string(processed_img, config='--psm 6')
                data = parse_ride_data(text, app)
                final_data[app] = data
                print(f"  -> Found: {data}")
            else:
                print(f"  -> Error: Could not process image")
        else:
            print(f"  -> File not found: {path}")

    save_to_file(final_data)

if __name__ == "__main__":
    main()
