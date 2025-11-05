import { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = 'http://localhost:5000/api'

function App() {
  const [tasks, setTasks] = useState([])
  const [taskName, setTaskName] = useState('')
  const [loading, setLoading] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editingName, setEditingName] = useState('')

  useEffect(() => {
    fetchTasks()
  }, [])

  const fetchTasks = async () => {
    try {
      const response = await axios.get(`${API_URL}/tasks`)
      setTasks(response.data.tasks)
    } catch (error) {
      console.error('Error fetching tasks:', error)
    }
  }

  const addTask = async (e) => {
    e.preventDefault()
    
    if (!taskName.trim()) return
    
    setLoading(true)
    try {
      const response = await axios.post(`${API_URL}/tasks`, {
        name: taskName
      })
      setTasks([...tasks, response.data.task])
      setTaskName('')
    } catch (error) {
      console.error('Error adding task:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleComplete = async (taskId) => {
    try {
      const response = await axios.patch(`${API_URL}/tasks/${taskId}/complete`)
      setTasks(tasks.map(task => 
        task.id === taskId ? response.data.task : task
      ))
    } catch (error) {
      console.error('Error toggling task:', error)
    }
  }

  const startEditing = (task) => {
    setEditingId(task.id)
    setEditingName(task.name)
  }

  const cancelEditing = () => {
    setEditingId(null)
    setEditingName('')
  }

  const saveEdit = async (taskId) => {
    if (!editingName.trim()) return
    
    try {
      const response = await axios.put(`${API_URL}/tasks/${taskId}`, {
        name: editingName
      })
      setTasks(tasks.map(task => 
        task.id === taskId ? response.data.task : task
      ))
      setEditingId(null)
      setEditingName('')
    } catch (error) {
      console.error('Error updating task:', error)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8 max-w-2xl">
        <h1 className="text-4xl font-bold text-center text-gray-800 mb-8">
          Task Manager
        </h1>

        {/* Add Task Form */}
        <form onSubmit={addTask} className="mb-8">
          <div className="flex gap-2">
            <input
              type="text"
              value={taskName}
              onChange={(e) => setTaskName(e.target.value)}
              placeholder="Enter a new task..."
              className="flex-1 px-4 py-3 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !taskName.trim()}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
            >
              Add
            </button>
          </div>
        </form>

        {/* Task List */}
        <div className="bg-white rounded-lg shadow-md">
          {tasks.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No tasks yet. Add your first task above!
            </div>
          ) : (
            <ul className="divide-y divide-gray-200">
              {tasks.map((task) => (
                <li key={task.id} className="p-4 hover:bg-gray-50 transition-colors">
                  {editingId === task.id ? (
                    // Edit Mode
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        className="flex-1 px-3 py-2 border border-blue-500 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') saveEdit(task.id)
                          if (e.key === 'Escape') cancelEditing()
                        }}
                      />
                      <button
                        onClick={() => saveEdit(task.id)}
                        className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors text-sm font-medium"
                      >
                        Save
                      </button>
                      <button
                        onClick={cancelEditing}
                        className="px-3 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors text-sm font-medium"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    // View Mode
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={task.status === 'completed'}
                        onChange={() => toggleComplete(task.id)}
                        className="w-5 h-5 text-blue-600 rounded focus:ring-2 focus:ring-blue-500 cursor-pointer"
                      />
                      <span className={`flex-1 ${task.status === 'completed' ? 'line-through text-gray-400' : 'text-gray-800'}`}>
                        {task.name}
                      </span>
                      <button
                        onClick={() => startEditing(task)}
                        className="px-3 py-1 text-blue-600 hover:bg-blue-50 rounded transition-colors text-sm font-medium"
                      >
                        Edit
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
