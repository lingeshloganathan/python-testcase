import pytest
import requests
import pandas as pd
from datetime import datetime

def write_to_csv(csv_file, test_name, status, message=""):
    df = pd.DataFrame({
        "Test Name": [test_name],
        "Status": [status],
        "Message": [message],
        "Timestamp": [datetime.now().isoformat()]
    })
    
    try:
        existing_df = pd.read_csv(csv_file)
        df = pd.concat([existing_df, df], ignore_index=True)
    except FileNotFoundError:
        pass
    
    df.to_csv(csv_file, index=False)

def test_health_check(api_url, csv_file):
    try:
        response = requests.get(f"{api_url}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        write_to_csv(csv_file, "Health Check", "PASSED")
    except Exception as e:
        write_to_csv(csv_file, "Health Check", "FAILED", str(e))
        raise

def test_get_tasks(api_url, csv_file):
    try:
        response = requests.get(f"{api_url}/tasks")
        assert response.status_code == 200
        tasks = response.json()["tasks"]
        assert isinstance(tasks, list)
        write_to_csv(csv_file, "Get Tasks List", "PASSED")
    except Exception as e:
        write_to_csv(csv_file, "Get Tasks List", "FAILED", str(e))
        raise

def test_task_workflow(api_url, csv_file):
    try:
        # Create task
        task_data = {"name": "Test Task"}
        response = requests.post(f"{api_url}/tasks", json=task_data)
        assert response.status_code == 201
        task = response.json()["task"]
        task_id = task["id"]
        write_to_csv(csv_file, "Create Task", "PASSED")

        # Update task
        update_data = {"name": "Updated Test Task"}
        response = requests.put(f"{api_url}/tasks/{task_id}", json=update_data)
        assert response.status_code == 200
        write_to_csv(csv_file, "Update Task", "PASSED")

        # Complete task
        response = requests.patch(f"{api_url}/tasks/{task_id}/complete")
        assert response.status_code == 200
        write_to_csv(csv_file, "Complete Task", "PASSED")

        # Delete task
        response = requests.delete(f"{api_url}/tasks/{task_id}")
        assert response.status_code == 200
        write_to_csv(csv_file, "Delete Task", "PASSED")

    except Exception as e:
        write_to_csv(csv_file, "Task Workflow", "FAILED", str(e))
        raise

def test_task_counts(api_url, csv_file):
    try:
        response = requests.get(f"{api_url}/tasks/count")
        assert response.status_code == 200
        counts = response.json()
        assert all(k in counts for k in ["pending", "completed", "total"])
        write_to_csv(csv_file, "Task Counts", "PASSED")
    except Exception as e:
        write_to_csv(csv_file, "Task Counts", "FAILED", str(e))
        raise