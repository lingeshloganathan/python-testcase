import pytest
import sys
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

def main():
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--verbose')
    chrome_options.add_argument('--log-level=0')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    
    # Initialize Chrome WebDriver
    print("Setting up Chrome WebDriver...")
    service = Service(ChromeDriverManager().install())
    driver = None
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("Chrome WebDriver initialized successfully!")
        
        # Run the tests
        print("\nRunning tests...")
        pytest.main([
            "test_ui.py",
            "-v",
            "--html=test_report.html"
        ])
        
    except Exception as e:
        print(f"\nError during test execution: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        if driver:
            driver.quit()
            print("\nChrome WebDriver closed.")

if __name__ == "__main__":
    main()