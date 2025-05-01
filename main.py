import time
import pandas as pd
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from csv import DictReader
import json
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webelement import WebElement  # Import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import config as cf
from selenium_stealth import stealth
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import mysql.connector
import schedule
from datetime import datetime, timedelta, date
import re


con = mysql.connector.connect(
    host="localhost",
    user="root",
    password="admin",
    database="uber"
)

cursor = con.cursor()


# Query to Create Table
query = """CREATE TABLE if not exists uber_details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    route_from TEXT,
    route_to TEXT,
    ride_type TEXT,
    ride_max_persons FLOAT,
    ride_request_time TEXT,
    ride_waiting_time FLOAT,
    ride_request_date TEXT,
    ride_reaching_time TEXT,
    ride_time TEXT,
    ride_price DECIMAL(10, 2)
    )"""
cursor.execute(query)

#chrome_options = Options()

#chrome_options.add_argument("--disable-notifications")
user_data_dir = r"C:\Users\shree\AppData\Local\Google\Chrome\User Data"
profile_dir = "Profile 1"
#try from video
options = webdriver.ChromeOptions()
# options.add_argument("--disable-webrtc")
options.add_argument(f"user-data-dir={user_data_dir}")
options.add_argument(f"profile-directory={profile_dir}")

options.add_argument("--headless") 
# options.add_argument("--disable-gpu")  # Disable GPU acceleration
options.add_argument("--no-sandbox")  # Disable the sandbox (required for certain environments)
# options.add_argument("--disable-software-rasterizer")  # Disable software rasterizer
# options.add_argument("--use-gl=swiftshader")  # Use software rendering for WebGL
# options.add_argument("--disable-webrtc")  # Disable WebRTC




service = ChromeService(ChromeDriverManager().install())


def debuglog(statement=None,var=None):
    debug=False
    if debug:
        print(f"{statement} {var}")

def get_details(route, url):
    driver = webdriver.Chrome(service=service, options=options)

    # Set the page load timeout
    driver.set_page_load_timeout(20)  # Timeout after 10 seconds

    # Creating empty list to store the details of the routes
    routes_list = []

    try:
        driver.get(url)
        print('Route loaded')

        # Wait for a specific element to be present and visible before scraping
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div._css-zSrrc"))
        )

        # Wait explicitly for the specific elements that are required for data extraction
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "p._css-gmxjOK"))
        )

        # Now that the page is loaded, we can proceed with finding elements
        elements = driver.find_elements(By.CSS_SELECTOR, "div._css-zSrrc")

        # Loop through each element and extract details
        for element in elements:
            ride_type_person = element.find_element(By.CSS_SELECTOR, "p._css-gmxjOK").text
            ride_time = element.find_element(By.CSS_SELECTOR, "p._css-bNXHBf").text
            ride_price = element.find_element(By.CSS_SELECTOR, "p._css-iQlrzm").text
            debuglog("  ride_type_person:", ride_type_person)
            debuglog("  ride_time:", ride_time)
            debuglog("  ride_price:", ride_price)

            if ride_type_person[-1] == 'L':
                # Extract ride type and person
                ride_type = ride_type_person
                ride_person = 6
            else:
                ride_type = ride_type_person[:-1]  # remove last character
                ride_person = float(ride_type_person[-1])  # convert last character to int

            # Extract ride waiting time
            ride_waiting_time = float(ride_time.split(" ")[0])

            # Extract ride reaching time and convert to 24-hour format
            ride_reaching_time_str = re.search(r'\d{1,2}:\d{2} (AM|PM)', ride_time).group()
            ride_reaching_time = datetime.strptime(ride_reaching_time_str, "%I:%M %p")
            ride_reaching_time = ride_reaching_time.strftime("%H:%M:%S")

            # Get current time and date
            current_time = datetime.now()
            ride_request_time = current_time.strftime("%H:%M:%S")
            ride_request_date = current_time.strftime("%Y-%m-%d")

            # Calculate ride time
            ride_request_time_obj = datetime.strptime(ride_request_time, "%H:%M:%S")
            ride_reaching_time_obj = datetime.strptime(ride_reaching_time, "%H:%M:%S")
            ride_waiting_time_obj = timedelta(minutes=ride_waiting_time)
            ride_time_obj = ride_reaching_time_obj - (ride_request_time_obj + ride_waiting_time_obj)
            ride_time = str(ride_time_obj)

            # Transform ride price
            ride_price = float(ride_price.replace("₹", ""))
            # Transform route
            route_parts = route.split(" to ")
            route_from = route_parts[0]
            route_to = route_parts[1]

            route_item = {
                'route_from': route_from,
                'route_to': route_to,
                'ride_type': ride_type,
                'ride_max_persons': ride_person,
                'ride_request_time': ride_request_time,
                'ride_waiting_time': ride_waiting_time,
                'ride_request_date': ride_request_date,
                'ride_reaching_time': ride_reaching_time,
                'ride_time': ride_time,
                'ride_price': ride_price
            }

            routes_list.append(route_item)
            # print(routes_list)

        

    except Exception as e:
        print('Page load timed out or encountered an error:', str(e))
        return None

    finally:
        # Once all details are got for a route, we convert it to a dataframe so that we can write it to the db
        df = pd.DataFrame(routes_list)
        # Ensure that the browser is closed
        driver.quit()
        print(f"✅ Success")

        return df



def write_into_db(df):
    query = """INSERT INTO uber_details (
        route_from,
        route_to,
        ride_type,
        ride_max_persons,
        ride_request_time,
        ride_waiting_time,
        ride_request_date,
        ride_reaching_time,
        ride_time,
        ride_price
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    result = []

    if df is not None:
        for index in df.index:
            row_data = list(df.loc[index].values)
            result.append(row_data)
        cursor.executemany(query,
                           result)  # execute many and storing data in list as it connects to the db once it finishes
        # getting input rather than each time
        con.commit()

    else:
        print("DataFrame is None, cannot process.")



 


route_urls = {
    "Chennai Lighthouse to Chennai Citi Centre": "https://m.uber.com/go/product-selection?drop%5B0%5D=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&effect=&pickup=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&uclick_id=174784cc-5ad8-418b-ac1c-c41d7bc78b89&vehicle=2019",
    "Chennai Citi Centre to Chennai Lighthouse": "https://m.uber.com/go/product-selection?drop%5B0%5D=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&effect=&pickup=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%22No.%2010%20and%2011%2C%20Dr%20Radhakrishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20TN%20600004%22%2C%22id%22%3A%22ea74162a-529a-7e81-5c88-4e012afddc0a%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429486%2C%22longitude%22%3A80.2738015%2C%22provider%22%3A%22uber_places%22%7D&uclick_id=174784cc-5ad8-418b-ac1c-c41d7bc78b89&vehicle=2019",
    "Express Avenue Mall to Chennai Lighthouse": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Lighthouse to Express Avenue Mall": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Lighthouse to PVR Ampa SkyOne": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22PVR%20Ampa%20SkyOne%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJyzSdtIRmUjoRqkjefEktGWk%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736743%2C%22longitude%22%3A80.2212248%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "PVR Ampa SkyOne to Chennai Lighthouse": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22PVR%20Ampa%20SkyOne%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJyzSdtIRmUjoRqkjefEktGWk%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736743%2C%22longitude%22%3A80.2212248%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Marina Beach to Chennai Lighthouse": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Lighthouse to Marina Beach": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Lighthouse to Semmozhi Poonga": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Semmozhi Poonga to Chennai Lighthouse": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Sai Baba Temple Mylapore to Chennai Lighthouse": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Lighthouse to Sai Baba Temple Mylapore": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Chennai%20Lighthouse%22%2C%22addressLine2%22%3A%22Marina%20Beach%20Road%2C%20Marina%20Beach%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ5dptVYBoUjoRCQL97Hq9F1w%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0397354%2C%22longitude%22%3A80.2792984%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Citi Centre to Express Avenue Mall": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Express Avenue Mall to Chennai Citi Centre": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "PVR Ampa SkyOne to Chennai Citi Centre": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Ampa%20Skyone%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJZ7WProRmUjoRRAt0jFusLw8%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736821%2C%22longitude%22%3A80.2212825%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Citi Centre to PVR Ampa SkyOne": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Ampa%20Skyone%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJZ7WProRmUjoRRAt0jFusLw8%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736821%2C%22longitude%22%3A80.2212825%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Citi Centre to Marina Beach": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Marina Beach to Chennai Citi Centre": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Semmozhi Poonga to Chennai Citi Centre": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Citi Centre to Semmozhi Poonga": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Chennai Citi Centre to Sai Baba Temple Mylapore": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Sai Baba Temple Mylapore to Chennai Citi Centre": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22CHENNAI%20CITI%20CENTRE%22%2C%22addressLine2%22%3A%2210%2F11%2C%20Dr%20Radha%20Krishnan%20Salai%2C%20Loganathan%20Colony%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJ8X9W6P9nUjoR1PQDf-g24qg%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0429239%2C%22longitude%22%3A80.27377170000001%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Express Avenue Mall to PVR Ampa SkyOne": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Ampa%20Skyone%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJZ7WProRmUjoRRAt0jFusLw8%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736821%2C%22longitude%22%3A80.2212825%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "PVR Ampa SkyOne to Express Avenue Mall": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22PVR%20Ampa%20SkyOne%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJyzSdtIRmUjoRqkjefEktGWk%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736743%2C%22longitude%22%3A80.2212248%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Express Avenue Mall to Marina Beach": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Marina Beach to Express Avenue Mall": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Semmozhi Poonga to Express Avenue Mall": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Express Avenue Mall to Semmozhi Poonga": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Sai Baba Temple Mylapore to Express Avenue Mall": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Express Avenue Mall to Sai Baba Temple Mylapore": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Express%20Avenue%20Mall%22%2C%22addressLine2%22%3A%22Whites%20Rd%2C%20Express%20Estate%2C%20Royapettah%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJgaOxaT1mUjoR_q0IaoVAKvE%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0583826%2C%22longitude%22%3A80.2641598%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "PVR Ampa SkyOne to Marina Beach": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22PVR%20Ampa%20SkyOne%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJyzSdtIRmUjoRqkjefEktGWk%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736743%2C%22longitude%22%3A80.2212248%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Marina Beach to PVR Ampa SkyOne": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22PVR%20Ampa%20SkyOne%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJyzSdtIRmUjoRqkjefEktGWk%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736743%2C%22longitude%22%3A80.2212248%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Semmozhi Poonga to PVR Ampa SkyOne": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22PVR%20Ampa%20SkyOne%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJyzSdtIRmUjoRqkjefEktGWk%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736743%2C%22longitude%22%3A80.2212248%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "PVR Ampa SkyOne to Semmozhi Poonga": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22PVR%20Ampa%20SkyOne%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJyzSdtIRmUjoRqkjefEktGWk%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736743%2C%22longitude%22%3A80.2212248%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "PVR Ampa SkyOne to Sai Baba Temple Mylapore": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22PVR%20Ampa%20SkyOne%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJyzSdtIRmUjoRqkjefEktGWk%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736743%2C%22longitude%22%3A80.2212248%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Sai Baba Temple Mylapore to PVR Ampa SkyOne": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22PVR%20Ampa%20SkyOne%22%2C%22addressLine2%22%3A%221%2C%20Nelson%20Manickam%20Rd%2C%20Aminjikarai%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJyzSdtIRmUjoRqkjefEktGWk%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0736743%2C%22longitude%22%3A80.2212248%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Sai Baba Temple Mylapore to Marina Beach": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Marina Beach to Sai Baba Temple Mylapore": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Semmozhi Poonga to Sai Baba Temple Mylapore": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Sai Baba Temple Mylapore to Semmozhi Poonga": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Sai%20Baba%20Temple%20Mylapore%22%2C%22addressLine2%22%3A%2227M7%2B4VF%2C%20Venkatesa%20Agraharam%20Rd%2C%20Kabali%20Nagar%2C%20Venkatesa%20Agraharam%2C%20Mylapore%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJFwDbhM1nUjoR9lMVvvVD89o%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0328131%2C%22longitude%22%3A80.26467889999999%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Marina Beach to Semmozhi Poonga": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019",
    "Semmozhi Poonga to Marina Beach": "https://m.uber.com/go/product-selection?_gl=1%2Anu74i5%2A_gcl_au%2ANTEyODIxMTIyLjE3MjU4NjExNzg.%2A_ga%2ANTU1NzI2MzIuMTcyNTcxNTczNw..%2A_ga_XTGQLY6KPT%2AMTcyNTkzODkwMS4xMS4xLjE3MjU5NDAxOTguMC4wLjA.&drop%5B0%5D=%7B%22addressLine1%22%3A%22Marina%20Beach%22%2C%22addressLine2%22%3A%22Tamil%20Nadu%22%2C%22id%22%3A%22ChIJuzIBtptoUjoRCrZi347PSQU%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0499526%2C%22longitude%22%3A80.2824026%2C%22provider%22%3A%22google_places%22%7D&marketing_vistor_id=95dd8594-7619-4d77-b0e1-c3ca5ff6776f&pickup=%7B%22addressLine1%22%3A%22Semmozhi%20Poonga%22%2C%22addressLine2%22%3A%223722%2B6H7%2C%20Cathedral%20Rd%2C%20opposite%20American%20Consulate%2C%20Ellaiamman%20Colony%2C%20Teynampet%2C%20Chennai%2C%20Tamil%20Nadu%22%2C%22id%22%3A%22ChIJcVcO_UZmUjoR21emTXt0U4k%22%2C%22source%22%3A%22SEARCH%22%2C%22latitude%22%3A13.0505371%2C%22longitude%22%3A80.2514128%2C%22provider%22%3A%22google_places%22%7D&uclick_id=e6e110fb-7ff2-4d6b-bebd-37dce42603ef&vehicle=2019"
}

def fetch_and_write_details():
    current_time = datetime.now().strftime("%H:%M")
    print(f"Running fetch_and_write_details function at {current_time}...")
    i=1
    for key, value in route_urls.items():
        print(f"Iteration {i}/42: Fetching data from key: {key}")
        i += 1
        df = get_details(key, value)
        write_into_db(df)

def wait_until_next_interval():
    now = datetime.now()
    current_minute = now.minute

    # Define the stop and start times
    stop_time = now.replace(hour=23, minute=0, second=0, microsecond=0)
    start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)

    # Determine if we should stop for the night
    if now > stop_time:
        # If it's past 11:00 PM, calculate the wait time until 7:00 AM next day
        next_start = start_time + timedelta(days=1)
        wait_time = (next_start - now).total_seconds()
        print(f"Waiting for {wait_time} seconds until {next_start}")
        time.sleep(wait_time)
        return

    # Calculate the next hour mark
    next_interval = now.replace(minute=0, second=0, microsecond=0)
    if now.minute >= 0:
        next_interval += timedelta(hours=1)

    # If next_interval is after 11:00 PM, wait until 7:00 AM the next day
    if next_interval > stop_time:
        next_start = start_time + timedelta(days=1)
        wait_time = (next_start - now).total_seconds()
        print(f"Waiting for {wait_time} seconds until {next_start}")
        time.sleep(wait_time)
        return

    wait_time = (next_interval - now).total_seconds()
    print(f"Waiting for {wait_time} seconds until {next_interval}")
    time.sleep(wait_time)

while True:
    fetch_and_write_details()  # Perform the task
    wait_until_next_interval()  # Wait until the next top-of-hour mark
