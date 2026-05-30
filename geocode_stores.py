"""
Run this locally:
    pip install requests pandas openpyxl
    python geocode_stores.py

Output: saree_master_geocoded.csv — drop this into the app folder.
"""
import time, requests, pandas as pd

MAPBOX_TOKEN = "YOUR_MAPBOX_TOKEN_HERE"
INPUT_FILE   = "saree_master_clean.csv"
OUTPUT_FILE  = "saree_master_geocoded.csv"

INTL_COUNTRY = {"Oman":"om","Qatar":"qa","UAE":"ae","Singapore":"sg",
                "UK":"gb","USA":"us","Canada":"ca","Australia":"au"}

def geocode(query, country=None):
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{requests.utils.quote(query)}.json"
    params = {"access_token": MAPBOX_TOKEN, "limit": 1}
    if country:
        params["country"] = country
    try:
        r = requests.get(url, params=params, timeout=10)
        features = r.json().get("features", [])
        if features:
            lng, lat = features[0]["center"]
            return round(lat, 6), round(lng, 6)
    except Exception as e:
        print(f"    Error: {e}")
    return None, None

df = pd.read_csv(INPUT_FILE)
total = len(df)
lats, lngs, methods = [], [], []
failed = []

for i, row in df.iterrows():
    state    = str(row["State"]).strip()
    city     = str(row["City"]).strip()
    remaining = str(row["Remaining Address"]).strip()
    pincode  = str(row["Pincode"]).strip()
    country  = INTL_COUNTRY.get(state, "in")

    if country != "in":
        query = f"{remaining}, {city}, {state}"
    else:
        query = f"{remaining}, {city}, {state} {pincode}, India"

    print(f"[{i+1}/{total}] {row['Store Name'][:55]}...")
    lat, lng = geocode(query, country)
    method = "full_address"

    if lat is None:
        fallback = f"{city}, {state}" + ("" if country != "in" else ", India")
        print(f"  fallback: {fallback}")
        lat, lng = geocode(fallback, country)
        method = "city_fallback"

    if lat is None:
        print(f"  !! FAILED")
        failed.append(row["Store Name"])
        method = "failed"
    else:
        print(f"  -> {lat}, {lng}")

    lats.append(lat); lngs.append(lng); methods.append(method)
    time.sleep(0.12)

df["lat"] = lats
df["lng"] = lngs
df["geocode_method"] = methods
df.to_csv(OUTPUT_FILE, index=False)

print(f"\nDone. {total - len(failed)}/{total} succeeded.")
if failed:
    print("Failed:", failed)
print(f"Saved to {OUTPUT_FILE}")
