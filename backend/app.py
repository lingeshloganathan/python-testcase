from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

# In-memory storage (will be replaced with database later)
tasks = []

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    # Sort by created_at to ensure order of creation
    sorted_tasks = sorted(tasks, key=lambda x: x['created_at'])
    return jsonify({'tasks': sorted_tasks})

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)

