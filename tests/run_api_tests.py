import pytest
import requests
import time
import os

def wait_for_api(url, max_retries=5):
    print(f"Checking API availability at {url}")
    for i in range(max_retries):
        try:
            response = requests.get(f"{url}/health")
            if response.status_code == 200:
                print("API is running!")
                return True
        except requests.exceptions.ConnectionError:
            print(f"API not ready, attempt {i + 1}/{max_retries}")
            time.sleep(2)
    return False

def main():
    api_url = "http://localhost:5000/api"
    
    # Wait for API to be available
    if not wait_for_api(api_url):
        print("Error: API is not running. Please start the backend server first.")
        return
    
    # Run the tests
    print("\nRunning API tests...")
    pytest.main([
        "test_api.py",
        "-v",
        "--html=api_test_report.html"
    ])

if __name__ == "__main__":
    main()