import { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = 'http://localhost:5000/api'
const STORAGE_KEY = 'taskManager_tasks'

function App() {
  const [tasks, setTasks] = useState([])
  const [taskName, setTaskName] = useState('')
  const [loading, setLoading] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editingName, setEditingName] = useState('')
  const [filter, setFilter] = useState('all') // 'all', 'pending', 'completed'

  // Load tasks from localStorage on mount
  useEffect(() => {
    const savedTasks = localStorage.getItem(STORAGE_KEY)
    if (savedTasks) {
      try {
        setTasks(JSON.parse(savedTasks))
      } catch (error) {
        console.error('Error loading tasks from localStorage:', error)
        fetchTasks()
      }
    } else {
      fetchTasks()
    }
  }, [])

  // Save tasks to localStorage whenever they change
  useEffect(() => {
    if (tasks.length > 0 || localStorage.getItem(STORAGE_KEY)) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks))
    }
  }, [tasks])

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

  const deleteTask = async (taskId) => {
    if (!window.confirm('Are you sure you want to delete this task?')) {
      return
    }
    
    try {
      await axios.delete(`${API_URL}/tasks/${taskId}`)
      setTasks(tasks.filter(task => task.id !== taskId))
    } catch (error) {
      console.error('Error deleting task:', error)
    }
  }

  const clearCompleted = async () => {
    const completedCount = tasks.filter(t => t.status === 'completed').length
    
    if (completedCount === 0) {
      alert('No completed tasks to clear')
      return
    }
    
    if (!window.confirm(`Clear ${completedCount} completed task(s)?`)) {
      return
    }
    
    try {
      await axios.delete(`${API_URL}/tasks/completed`)
      setTasks(tasks.filter(task => task.status !== 'completed'))
    } catch (error) {
      console.error('Error clearing completed tasks:', error)
    }
  }

  // Filter tasks based on selected filter
  const filteredTasks = tasks.filter(task => {
    if (filter === 'all') return true
    if (filter === 'pending') return task.status === 'pending'
    if (filter === 'completed') return task.status === 'completed'
    return true
  })

  const hasCompletedTasks = tasks.some(task => task.status === 'completed')

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

        {/* Filter Buttons */}
        {tasks.length > 0 && (
          <div className="mb-4 flex gap-2 justify-center">
            <button
              onClick={() => setFilter('all')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                filter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-100'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilter('pending')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                filter === 'pending'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-100'
              }`}
            >
              Pending
            </button>
            <button
              onClick={() => setFilter('completed')}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                filter === 'completed'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-100'
              }`}
            >
              Completed
            </button>
          </div>
        )}

        {/* Clear Completed Button */}
        {hasCompletedTasks && (
          <div className="mb-4 flex justify-end">
            <button
              onClick={clearCompleted}
              className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors font-medium text-sm"
            >
              Clear Completed
            </button>
          </div>
        )}

        {/* Task List */}
        <div className="bg-white rounded-lg shadow-md">
          {filteredTasks.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              {tasks.length === 0
                ? 'No tasks yet. Add your first task above!'
                : `No ${filter} tasks`}
            </div>
          ) : (
            <ul className="divide-y divide-gray-200">
              {filteredTasks.map((task) => (
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
                      <button
                        onClick={() => deleteTask(task.id)}
                        className="px-3 py-1 text-red-600 hover:bg-red-50 rounded transition-colors text-sm font-medium"
                      >
                        Delete
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