from seleniumwire import webdriver  # pip install selenium-wire
from selenium.webdriver.chrome.options import Options
import logging

URL = "https://www.aerolineas.com.ar/"

def get_token_with_selenium_wire():
    logging.info("Starting Selenium Wire to fetch token from network requests...")
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    driver.get(URL)

    token = None
    for request in driver.requests:
        if request.response and "api.aerolineas.com.ar" in request.url:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split("Bearer ")[1]
                logging.info(f"Token found in request to {request.url}")
                break
    driver.quit()
    return token