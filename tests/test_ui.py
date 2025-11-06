import pytest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
from datetime import datetime
import time
import traceback
import os
import sys

@pytest.fixture(scope="session")
def driver():
    print("\nSetting up Chrome WebDriver...")
    print(f"Python version: {sys.version}")
    print(f"Selenium version: {webdriver.__version__}")
    
    # Check Chrome installation
    print("\nChecking Chrome installation...")
    chrome_path = None
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.environ.get('PROGRAMFILES', '') + r"\Google\Chrome\Application\chrome.exe",
        os.environ.get('PROGRAMFILES(X86)', '') + r"\Google\Chrome\Application\chrome.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            chrome_path = path
            print(f"Chrome found at: {chrome_path}")
            break
    
    if not chrome_path:
        raise Exception("Chrome not found! Please install Google Chrome.")
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--start-maximized')  # Start with maximized window
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    # Initialize ChromeDriver
    print("\nInitializing Chrome WebDriver...")
    driver_path = ChromeDriverManager().install()
    print(f"ChromeDriver path: {driver_path}")
    
    # Create and return the driver
    driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
    yield driver
    driver.quit()

def write_to_csv(csv_file, test_name, status, message="", test_case_id=""):
    df = pd.DataFrame({
        "Test Case ID": [test_case_id],
        "Test Name": [test_name],
        "Status": [status],
        "Message": [message],
        "Timestamp": [datetime.now().isoformat()]
    })

    file_exists = os.path.exists(csv_file)
    df.to_csv(csv_file, mode='a', header=not file_exists, index=False)

def test_ui_load(driver, csv_file):
    try:
        print("\nStarting UI Load Test...")
        url = "http://localhost:5173"
        print(f"Navigating to: {url}")
        driver.get(url)
        
        # Wait for the page to load
        print("Waiting for container element...")
        container = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "container"))
        )
        print("Container element found!")
        
        # Highlight the container element
        driver.execute_script(
            "arguments[0].style.border='3px solid red';",
            container
        )
        time.sleep(1)  # Pause to see the highlight
        
        # Take a screenshot for verification
        screenshot_path = os.path.join(os.path.dirname(__file__), "ui_load_test.png")
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
        
        write_to_csv(csv_file, "UI Load", "PASSED", test_case_id="TC-17")
    except Exception as e:
        write_to_csv(csv_file, "UI Load", "FAILED", traceback.format_exc(), test_case_id="TC-17")
        raise

def test_add_task(driver, csv_file):
    try:
        print("\nStarting Add Task Test...")
        # Wait for and find task input
        print("Looking for task input field...")
        task_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter a new task...']"))
        )
        
        # Highlight the input field
        driver.execute_script(
            "arguments[0].style.border='3px solid green';",
            task_input
        )
        time.sleep(1)  # Pause to see the highlight
        
        print("Found task input, entering text...")
        task_input.clear()
        time.sleep(1)  # Small pause for stability
        task_input.send_keys("UI Test Task")
        
        # Wait for and click add button
        print("Looking for Add Task button...")
        add_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add Task')]"))
        )
        print("Found Add Task button, clicking...")
        driver.execute_script("arguments[0].click();", add_button)
        
        # Verify task was added
        print("Waiting for task to appear in the list...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'UI Test Task')]"))
        )
        print("Task successfully added!")
        
        # Take a screenshot
        screenshot_path = "add_task_test.png"
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
        
        write_to_csv(csv_file, "Add Task UI", "PASSED", test_case_id="TC-01")
    except Exception as e:
        write_to_csv(csv_file, "Add Task UI", "FAILED", traceback.format_exc(), test_case_id="TC-01")
        raise

def test_complete_task(driver, csv_file):
    try:
        print("\nStarting Complete Task Test...")
        # Find and highlight checkbox
        print("Looking for checkbox...")
        checkbox = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='checkbox']"))
        )
        
        # Highlight the checkbox
        driver.execute_script(
            "arguments[0].style.outline='3px solid blue';",
            checkbox
        )
        time.sleep(1)  # Pause to see the highlight
        
        print("Clicking checkbox...")
        checkbox.click()
        time.sleep(1)  # Wait to see the effect
        
        # Verify task is completed
        print("Verifying task completion...")
        time.sleep(2)  # Wait for transition to complete
        
        def check_task_completed(driver):
            try:
                task_element = driver.find_element(By.XPATH, "//span[contains(text(), 'UI Test Task')]/..")
                html = task_element.get_attribute('outerHTML')
                print(f"HTML: {html}")
                
                classes = task_element.get_attribute("class")
                print(f"Parent Classes: {classes}")
                
                return "line-through" in html or "completed" in html.lower()
            except Exception as e:
                print(f"Error checking completion: {str(e)}")
                return False
        
        # Take a screenshot before checking
        driver.save_screenshot("before_completion_check.png")
        
        WebDriverWait(driver, 10).until(check_task_completed)
        print("Task completion verified!")
        
        # Highlight the completed task
        task_span = driver.find_element(By.XPATH, "//span[contains(text(), 'UI Test Task')]")
        driver.execute_script(
            "arguments[0].style.backgroundColor='#e8f5e9';",
            task_span
        )
        time.sleep(1)  # Pause to see the highlight
        
        # Take a screenshot
        screenshot_path = os.path.join(os.path.dirname(__file__), "complete_task_test.png")
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
        
        write_to_csv(csv_file, "Complete Task UI", "PASSED", test_case_id="TC-04")
    except Exception as e:
        write_to_csv(csv_file, "Complete Task UI", "FAILED", traceback.format_exc(), test_case_id="TC-04")
        raise

def test_filter_tasks(driver, csv_file):
    try:
        print("\nStarting Filter Tasks Test...")
        
        # Test completed filter
        print("Testing 'Completed' filter...")
        completed_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Completed']"))
        )
        driver.execute_script("arguments[0].style.backgroundColor='#e3f2fd';", completed_button)
        time.sleep(1)
        completed_button.click()
        time.sleep(2)  # Wait to see filtered results
        
        # Test pending filter
        print("Testing 'Pending' filter...")
        pending_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Pending']"))
        )
        driver.execute_script("arguments[0].style.backgroundColor='#fce4ec';", pending_button)
        time.sleep(1)
        pending_button.click()
        time.sleep(2)  # Wait to see filtered results
        
        # Test all filter
        print("Testing 'All' filter...")
        all_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='All']"))
        )
        driver.execute_script("arguments[0].style.backgroundColor='#f3e5f5';", all_button)
        time.sleep(1)
        all_button.click()
        time.sleep(2)  # Wait to see filtered results
        
        # Take a final screenshot
        screenshot_path = os.path.join(os.path.dirname(__file__), "filter_tasks_test.png")
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to: {screenshot_path}")
        
        write_to_csv(csv_file, "Filter Tasks UI", "PASSED", test_case_id="TC-11")
    except Exception as e:
        write_to_csv(csv_file, "Filter Tasks UI", "FAILED", traceback.format_exc(), test_case_id="TC-11")
        raise