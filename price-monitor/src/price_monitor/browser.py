from __future__ import annotations

import os

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions


def _configure(options):
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1800")
    options.add_argument("--lang=pt-BR")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    )
    return options


def build_driver():
    """Prefere Chrome e usa Edge como fallback no Windows."""
    chrome = _configure(ChromeOptions())
    binary = os.getenv("CHROME_BIN")
    if binary:
        chrome.binary_location = binary
    try:
        driver = webdriver.Chrome(options=chrome)
        driver.set_page_load_timeout(45)
        return driver
    except WebDriverException as chrome_error:
        edge = _configure(EdgeOptions())
        try:
            driver = webdriver.Edge(options=edge)
            driver.set_page_load_timeout(45)
            return driver
        except WebDriverException:
            raise chrome_error
