import time
import csv
import re
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Constants
LISTING_SELECTOR = "div.Nv2PK"
NAME_SELECTOR = "h1.DUwDvf"
CATEGORY_SELECTOR = "button.DkEaL"
ADDRESS_SELECTOR = "button[data-item-id='address']"
PHONE_SELECTOR = "button[data-item-id^='phone:tel']"
FEED_SELECTOR = "div[role='feed']"
DATABASE_FILENAME = "all_leads.csv" 

def setup_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--lang=en")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def save_to_local_database(data: List[Dict]):
    filename = DATABASE_FILENAME
    fieldnames = ["timestamp", "search_keyword", "name", "category", "phone", "address", "rating", "reviews"]
    
    existing_names = set()
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'name' in row:
                    existing_names.add(row['name'].strip().lower())

    new_leads = [d for d in data if d['name'].strip().lower() not in existing_names]

    if new_leads:
        file_exists = os.path.isfile(filename)
        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_leads)
        print(f"✅ Successfully appended {len(new_leads)} new leads.")

def scrape_google_maps(keyword: str, max_results: int = 15, check_stop=None):
    driver = setup_driver()
    wait = WebDriverWait(driver, 20)
    results = []
    seen_names = set()
    
    try:
        url = f"https://www.google.com/maps/search/{keyword.replace(' ', '+')}"
        driver.get(url)
        
        try:
            time.sleep(2)
            driver.find_element(By.XPATH, "//button[//span[contains(text(), 'Accept all')]]").click()
            time.sleep(2)
        except: pass

        while len(results) < max_results:
            # --- CRITICAL STOP CHECK 1 ---
            if check_stop and check_stop():
                print("🛑 STOP REQUESTED BY USER. Closing browser...")
                break

            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, LISTING_SELECTOR)))
                listings = driver.find_elements(By.CSS_SELECTOR, LISTING_SELECTOR)
            except: break

            if len(results) >= len(listings):
                try:
                    feed = driver.find_element(By.CSS_SELECTOR, "div[role='feed']")
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", feed)
                    time.sleep(3)
                    listings = driver.find_elements(By.CSS_SELECTOR, LISTING_SELECTOR)
                    if len(results) >= len(listings): break
                except: break

            try:
                # --- CRITICAL STOP CHECK 2 ---
                if check_stop and check_stop(): break

                target = listings[len(results)]
                card_rating = "N/A"
                try: card_rating = target.find_element(By.CSS_SELECTOR, "span.MW4etd").text.strip()
                except: pass

                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
                time.sleep(1)
                target.click()
                time.sleep(3)

                # --- CRITICAL STOP CHECK 3 ---
                if check_stop and check_stop(): break

                name = "N/A"
                try:
                    name_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, NAME_SELECTOR)))
                    name = name_el.text.strip()
                except: pass
                
                if name != "N/A" and name not in seen_names:
                    def safe_get(sel):
                        try: return driver.find_element(By.CSS_SELECTOR, sel).text.strip()
                        except: return "N/A"

                    rating, reviews = card_rating, "0"
                    try:
                        rating_el = driver.find_element(By.CSS_SELECTOR, 'span[aria-label*="stars"]')
                        label = rating_el.get_attribute("aria-label")
                        match_r = re.search(r"(\d+[\.,]\d+|\d+)", label)
                        if match_r: rating = match_r.group(1).replace(",", ".")
                        
                        rev_el = driver.find_element(By.CSS_SELECTOR, 'span[aria-label*="reviews"]')
                        match_v = re.search(r"(\d+[\d,.]*)", rev_el.get_attribute("aria-label"))
                        if match_v: reviews = match_v.group(1)
                    except: pass

                    record = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "search_keyword": keyword,
                        "name": name,
                        "category": safe_get(CATEGORY_SELECTOR),
                        "phone": safe_get(PHONE_SELECTOR),
                        "address": safe_get(ADDRESS_SELECTOR),
                        "rating": f"{rating} ⭐" if rating != "N/A" else "N/A",
                        "reviews": f"{reviews} reviews" if reviews != "0" else "No reviews"
                    }

                    results.append(record)
                    seen_names.add(name)
                    print(f"✅ Extracted: {name}")
                else:
                    # Increment counter to move to next listing even if duplicate
                    results.append({"name": "N/A"})

            except Exception as e:
                print(f"⚠️ Error: {e}")
                results.append({"name": "N/A"})

        # Final save of whatever we gathered before stopping
        valid_results = [r for r in results if r.get('name') not in ["N/A"]]
        save_to_local_database(valid_results)
        return valid_results

    finally:
        driver.quit()