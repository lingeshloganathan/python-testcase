import pytest
import requests
import pandas as pd
from datetime import datetime
import os
import traceback

@pytest.fixture(scope="session")
def api_url():
    return "http://localhost:5000/api"

@pytest.fixture(scope="session")

def csv_file():
    # Create a timestamp-based CSV filename for API test results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)
    return os.path.join(results_dir, f"test_results.csv")

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

def test_health_check(api_url, csv_file):
    try:
        response = requests.get(f"{api_url}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        write_to_csv(csv_file, "Health Check", "PASSED")
    except Exception as e:
        write_to_csv(csv_file, "Health Check", "FAILED", traceback.format_exc())
        raise

def test_get_tasks(api_url, csv_file):
    try:
        response = requests.get(f"{api_url}/tasks")
        assert response.status_code == 200
        tasks = response.json()["tasks"]
        assert isinstance(tasks, list)
        write_to_csv(csv_file, "Get Tasks List", "PASSED", test_case_id="TC-03")
    except Exception as e:
        write_to_csv(csv_file, "Get Tasks List", "FAILED", traceback.format_exc(), test_case_id="TC-03")
        raise

def test_task_workflow(api_url, csv_file):
    try:
        # Create task
        task_data = {"name": "Test Task"}
        response = requests.post(f"{api_url}/tasks", json=task_data)
        assert response.status_code == 201
        task = response.json()["task"]
        task_id = task["id"]
        write_to_csv(csv_file, "Create Task", "PASSED", test_case_id="TC-01")

        # Update task
        update_data = {"name": "Updated Test Task"}
        response = requests.put(f"{api_url}/tasks/{task_id}", json=update_data)
        assert response.status_code == 200
        write_to_csv(csv_file, "Update Task", "PASSED", test_case_id="TC-06")

        # Complete task
        response = requests.patch(f"{api_url}/tasks/{task_id}/complete")
        assert response.status_code == 200
        write_to_csv(csv_file, "Complete Task", "PASSED", test_case_id="TC-04")

        # Delete task
        response = requests.delete(f"{api_url}/tasks/{task_id}")
        assert response.status_code == 200
        write_to_csv(csv_file, "Delete Task", "PASSED", test_case_id="TC-07")

    except Exception as e:
        write_to_csv(csv_file, "Task Workflow", "FAILED", traceback.format_exc(), test_case_id="TC-01,TC-06,TC-04,TC-07")
        raise

def test_task_counts(api_url, csv_file):
    try:
        response = requests.get(f"{api_url}/tasks/count")
        assert response.status_code == 200
        counts = response.json()
        assert all(k in counts for k in ["pending", "completed", "total"])
        write_to_csv(csv_file, "Task Counts", "PASSED", test_case_id="TC-14")
    except Exception as e:
        write_to_csv(csv_file, "Task Counts", "FAILED", traceback.format_exc(), test_case_id="TC-14")
        raise

def test_clear_all_tasks(api_url, csv_file):
    try:
        # Add some test tasks
        task1 = {"name": "Test Task 1"}
        task2 = {"name": "Test Task 2"}
        requests.post(f"{api_url}/tasks", json=task1)
        requests.post(f"{api_url}/tasks", json=task2)
        
        # Clear all tasks
        response = requests.delete(f"{api_url}/tasks/all")
        assert response.status_code == 200
        
        # Verify tasks are cleared
        response = requests.get(f"{api_url}/tasks")
        assert response.status_code == 200
        tasks = response.json()["tasks"]
        assert len(tasks) == 0
        
        write_to_csv(csv_file, "Clear All Tasks", "PASSED", test_case_id="TC-15")
    except Exception as e:
        write_to_csv(csv_file, "Clear All Tasks", "FAILED", traceback.format_exc(), test_case_id="TC-15")
        raise