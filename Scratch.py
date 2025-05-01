import time
import re
import pandas as pd
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

# Setup your Chrome profile path
user_data_dir = r"C:\Users\shree\AppData\Local\Google\Chrome\User Data"
profile_dir = "Profile 1"

# Chrome options
options = webdriver.ChromeOptions()
options.add_argument(f"user-data-dir={user_data_dir}")
options.add_argument(f"profile-directory={profile_dir}")
# Do NOT add headless mode – we want to see the GUI

# Optional: specify path to chromedriver if not in PATH
# Example: service = Service(executable_path="C:/path/to/chromedriver.exe")
service = Service()  # Assumes chromedriver is in PATH

driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(10)

url = "https://m.uber.com/go/product-selection?drop%5B0%5D=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&effect=&pickup=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&uclick_id=174784cc-5ad8-418b-ac1c-c41d7bc78b89&vehicle=2019"

try:
    driver.get(url)
    print("Uber page loaded")
    time.sleep(5)  # Wait for data to load
    
    elements = driver.find_elements(By.CSS_SELECTOR, "div._css-zSrrc")
    print(f"Found {len(elements)} ride options")

    rides = []
    for element in elements:
        print(element)
        ride_type_person = element.find_element(By.CSS_SELECTOR, "p._css-gmxjOK").text
        print("------------------------------")
        print(ride_type_person)
        print("------------------------------")
        ride_time = element.find_element(By.CSS_SELECTOR, "p._css-bNXHBf").text
        ride_price = element.find_element(By.CSS_SELECTOR, "p._css-iQlrzm").text
        print(f"\nRide Type: {ride_type_person}")
        print(f"ETA + Time: {ride_time}")
        print(f"Price: {ride_price}")
        # Clean the price string to remove unwanted characters (₹, commas, etc.)
        ride_price_cleaned = re.sub(r'[^\d.]', '', ride_price)  # This will remove everything except digits and dot
        
        # Convert to float
        ride_price_val = float(ride_price_cleaned)
        ride_price = ride_price_val

        print(f"\nRide Type: {ride_type_person}")
        print(f"ETA + Time: {ride_time}")
        print(f"Price: {ride_price}")

        # Parse ride_type and capacity
        if ride_type_person[-1] == 'L':
            ride_type = ride_type_person
            ride_person = 6.0
        else:
            ride_type = ride_type_person[:-1]
            ride_person = float(ride_type_person[-1])
        # Extract waiting time and reaching time
        ride_waiting_time = float(ride_time.split(" ")[0])
        reaching_time_str = re.search(r'\d{1,2}:\d{2} (AM|PM)', ride_time).group()
        ride_reaching_time = datetime.strptime(reaching_time_str, "%I:%M %p").strftime("%H:%M:%S")
        # Timestamps
        current_time = datetime.now()
        ride_request_time = current_time.strftime("%H:%M:%S")
        ride_request_date = current_time.strftime("%Y-%m-%d")

        ride_request_time_obj = datetime.strptime(ride_request_time, "%H:%M:%S")
        ride_reaching_time_obj = datetime.strptime(ride_reaching_time, "%H:%M:%S")
        ride_waiting_time_obj = timedelta(minutes=ride_waiting_time)
        ride_time_obj = ride_reaching_time_obj - (ride_request_time_obj + ride_waiting_time_obj)
        ride_duration = str(ride_time_obj)
        # ride_price_val = float(ride_price.replace("₹", "").replace(",", ""))

        ride = {
            "ride_type": ride_type,
            "ride_max_persons": ride_person,
            "ride_request_time": ride_request_time,
            "ride_request_date": ride_request_date,
            "ride_waiting_time (min)": ride_waiting_time,
            "ride_reaching_time": ride_reaching_time,
            "ride_duration": ride_duration,
            "ride_price": ride_price_val,
        }
        print(ride)
        rides.append(ride)

        print('4')
    print(rides)
    df = pd.DataFrame(rides)
    print("\n📊 Ride Data:")
    print(df)

except Exception as e:
    print("❌ Error:", e)

finally:
    
    df = pd.DataFrame(rides)
    print("\n📊 Ride Data:")
    print(df)
    print("Closing browser...")
    time.sleep(2)
    driver.quit()
