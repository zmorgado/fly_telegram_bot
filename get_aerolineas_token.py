import os
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
import logging

URL = "https://www.aerolineas.com.ar/"

def get_token_with_selenium_wire():
    logging.info("Iniciando Selenium Wire para obtener el token de las requests de red...")
    options = Options()
    options.add_argument("--headless")
    chrome_path = os.getenv("CHROME_PATH")
    if chrome_path:
        options.binary_location = chrome_path
    driver = webdriver.Chrome(options=options)
    driver.get(URL)

    token = None
    for request in driver.requests:
        if request.response and "api.aerolineas.com.ar" in request.url:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split("Bearer ")[1]
                logging.info(f"Token encontrado en request a {request.url}")
                break
    driver.quit()
    return token