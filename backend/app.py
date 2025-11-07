from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

# In-memory storage
tasks = []

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    status_filter = request.args.get('status')
    
    filtered_tasks = tasks
    
    if status_filter == 'completed':
        filtered_tasks = [t for t in tasks if t['status'] == 'completed']
    elif status_filter == 'pending':
        filtered_tasks = [t for t in tasks if t['status'] == 'pending']
    
    # Sort by created_at
    sorted_tasks = sorted(filtered_tasks, key=lambda x: x['created_at'])
    return jsonify({'tasks': sorted_tasks})

@app.route('/api/tasks/count', methods=['GET'])
def get_task_count():
    pending_count = len([t for t in tasks if t['status'] == 'pending'])
    completed_count = len([t for t in tasks if t['status'] == 'completed'])
    total_count = len(tasks)
    
    return jsonify({
        'pending': pending_count,
        'completed': completed_count,
        'total': total_count
    })

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Task name is required'}), 400
    
    task = {
        'id': str(uuid.uuid4()),
        'name': data['name'],
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    }
    
    tasks.append(task)
    return jsonify({'task': task}), 201

@app.route('/api/tasks/<task_id>/complete', methods=['PATCH'])
def complete_task(task_id):
    task = next((t for t in tasks if t['id'] == task_id), None)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    task['status'] = 'completed' if task['status'] == 'pending' else 'pending'
    
    return jsonify({'task': task})

@app.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    task = next((t for t in tasks if t['id'] == task_id), None)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Task name is required'}), 400
    
    task['name'] = data['name']
    
    return jsonify({'task': task})

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    global tasks
    task = next((t for t in tasks if t['id'] == task_id), None)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    tasks = [t for t in tasks if t['id'] != task_id]
    
    return jsonify({'message': 'Task deleted successfully'})

@app.route('/api/tasks/completed', methods=['DELETE'])
def clear_completed():
    global tasks
    tasks = [t for t in tasks if t['status'] != 'completed']
    return jsonify({'message': 'Completed tasks cleared successfully'})

@app.route('/api/tasks/all', methods=['DELETE'])
def clear_all_tasks():
    global tasks
    tasks.clear()  # Clear all tasks
    return jsonify({'message': 'All tasks cleared successfully'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)