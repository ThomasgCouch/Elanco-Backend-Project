import json
import time
import requests
import os 

BASE_URL = "https://dev-task.elancoapps.com/data"
MAX_RETRIES = 6
TIMEOUT_SECONDS = 10
RETRYABLE_STATUS = {429, 500, 502, 503,504} #temp errors worth retrying
OUTPUT_PATH = os.path.join("data", "raw_sightings.json")
def fetch_sightings():
    """Fetch all sightings, retrying with exponential backoff on temporary failures."""
    url = f"{BASE_URL}/tick-sightings"
    wait = 1 # second; doubles after each failed attempt

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT_SECONDS)
        except requests.exceptions.RequestException as e:
        #No response : No internet etc...
            print(f"Attempt {attempt}/{MAX_RETRIES}: network error ({e})")
        else:
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    #200 with a broken body is a failure so retry
                    print(f"Attempt {attempt}/{MAX_RETRIES}: response was not valid JSON")
                else:
                    print(f"Attempt {attempt}/{MAX_RETRIES}: success")
                    return data
        
            elif response.status_code in RETRYABLE_STATUS:
                print(f"Attempt {attempt}/{MAX_RETRIES}: got {response.status_code}, will retry")
                # if the server is taking longer just wait
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = int(retry_after)
            
            else:
                raise RuntimeError(
                    f"Unexpected status {response.status_code}: {response.text[:200]}"
                )
        
        if attempt < MAX_RETRIES:
            print(f"Waiting {wait}s before retrying...")
            time.sleep(wait)
            wait *= 2 # exponential backoff
        
    raise RuntimeError(f"Failed to fetch sightings after {MAX_RETRIES} attempts")

def save_raw(sightings, path=OUTPUT_PATH):
    """Save the raw API response to disk so cleaning can be re-run without re fetching"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sightings, f, indent=2, ensure_ascii = False)
        
if __name__ == "__main__":
    sightings = fetch_sightings()
    save_raw(sightings)
    print(f"Saved {len(sightings)} sightings to {OUTPUT_PATH}")