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
  const [filter, setFilter] = useState('all')

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

  const clearAllTasks = async () => {
    if (tasks.length === 0) {
      alert('No tasks to clear')
      return
    }
    
    if (!window.confirm(`Are you sure you want to clear all ${tasks.length} tasks? This action cannot be undone.`)) {
      return
    }
    
    try {
      await axios.delete(`${API_URL}/tasks/all`)
      setTasks([])
    } catch (error) {
      console.error('Error clearing all tasks:', error)
    }
  }

  const filteredTasks = tasks.filter(task => {
    if (filter === 'all') return true
    if (filter === 'pending') return task.status === 'pending'
    if (filter === 'completed') return task.status === 'completed'
    return true
  })

  const pendingCount = tasks.filter(task => task.status === 'pending').length
  const completedCount = tasks.filter(task => task.status === 'completed').length
  const totalCount = tasks.length

  const hasCompletedTasks = tasks.some(task => task.status === 'completed')

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      <div className="container mx-auto px-4 py-6 sm:py-8 md:py-12 max-w-4xl">
        {/* Header */}
        <div className="text-center mb-6 sm:mb-8">
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-gray-800 mb-2">
            Task Manager
          </h1>
          <p className="text-gray-600 text-sm sm:text-base">
            Organize your tasks efficiently
          </p>
        </div>

        {/* Task Counter */}
        {totalCount > 0 && (
          <div className="mb-6 sm:mb-8">
            <div className="bg-white rounded-xl shadow-lg p-4 sm:p-6">
              <div className="grid grid-cols-3 gap-4 sm:gap-6">
                <div className="text-center">
                  <div className="text-2xl sm:text-3xl md:text-4xl font-bold text-blue-600 mb-1">
                    {pendingCount}
                  </div>
                  <div className="text-xs sm:text-sm text-gray-600 uppercase tracking-wide font-medium">
                    Pending
                  </div>
                </div>
                <div className="text-center border-x border-gray-200">
                  <div className="text-2xl sm:text-3xl md:text-4xl font-bold text-green-600 mb-1">
                    {completedCount}
                  </div>
                  <div className="text-xs sm:text-sm text-gray-600 uppercase tracking-wide font-medium">
                    Completed
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-700 mb-1">
                    {totalCount}
                  </div>
                  <div className="text-xs sm:text-sm text-gray-600 uppercase tracking-wide font-medium">
                    Total
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Add Task Form */}
        <form onSubmit={addTask} className="mb-6 sm:mb-8">
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
            <input
              type="text"
              value={taskName}
              onChange={(e) => setTaskName(e.target.value)}
              placeholder="Enter a new task..."
              className="flex-1 px-4 py-3 sm:py-4 rounded-lg border-2 border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-sm sm:text-base"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !taskName.trim()}
              className="px-6 py-3 sm:py-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-all font-semibold shadow-md hover:shadow-lg text-sm sm:text-base whitespace-nowrap"
            >
              {loading ? 'Adding...' : 'Add Task'}
            </button>
          </div>
        </form>

        {/* Filter Buttons and Clear Completed */}
        {tasks.length > 0 && (
          <div className="mb-4 sm:mb-6 flex flex-col sm:flex-row justify-between items-center gap-3">
            <div className="flex gap-2 w-full sm:w-auto">
              <button
                onClick={() => setFilter('all')}
                className={`flex-1 sm:flex-none px-4 sm:px-6 py-2 sm:py-2.5 rounded-lg font-semibold transition-all text-sm sm:text-base ${
                  filter === 'all'
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'bg-white text-gray-700 hover:bg-gray-50 shadow'
                }`}
              >
                All
              </button>
              <button
                onClick={() => setFilter('pending')}
                className={`flex-1 sm:flex-none px-4 sm:px-6 py-2 sm:py-2.5 rounded-lg font-semibold transition-all text-sm sm:text-base ${
                  filter === 'pending'
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'bg-white text-gray-700 hover:bg-gray-50 shadow'
                }`}
              >
                Pending
              </button>
              <button
                onClick={() => setFilter('completed')}
                className={`flex-1 sm:flex-none px-4 sm:px-6 py-2 sm:py-2.5 rounded-lg font-semibold transition-all text-sm sm:text-base ${
                  filter === 'completed'
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'bg-white text-gray-700 hover:bg-gray-50 shadow'
                }`}
              >
                Completed
              </button>
            </div>
            
            <div className="flex gap-2 flex-col sm:flex-row">
              {hasCompletedTasks && (
                <button
                  onClick={clearCompleted}
                  className="w-full sm:w-auto px-4 sm:px-6 py-2 sm:py-2.5 text-red-600 hover:bg-red-50 bg-white rounded-lg transition-all font-semibold shadow text-sm sm:text-base"
                >
                  Clear Completed
                </button>
              )}
              {tasks.length > 0 && (
                <button
                  onClick={clearAllTasks}
                  className="w-full sm:w-auto px-4 sm:px-6 py-2 sm:py-2.5 text-red-700 hover:bg-red-100 bg-white rounded-lg transition-all font-semibold shadow text-sm sm:text-base border border-red-200"
                >
                  Clear All Tasks
                </button>
              )}
            </div>
          </div>
        )}

        {/* Task List */}
        <div className="bg-white rounded-xl shadow-lg overflow-hidden">
          {filteredTasks.length === 0 ? (
            <div className="p-8 sm:p-12 text-center">
              <div className="text-gray-400 mb-4">
                <svg className="w-16 h-16 sm:w-20 sm:h-20 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <p className="text-gray-500 text-base sm:text-lg">
                {tasks.length === 0
                  ? 'No tasks yet. Add your first task above!'
                  : `No ${filter} tasks`}
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-200">
              {filteredTasks.map((task) => (
                <li key={task.id} className="p-3 sm:p-4 hover:bg-gray-50 transition-colors">
                  {editingId === task.id ? (
                    // Edit Mode
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                      <input
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        className="flex-1 px-3 py-2 border-2 border-blue-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm sm:text-base"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') saveEdit(task.id)
                          if (e.key === 'Escape') cancelEditing()
                        }}
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => saveEdit(task.id)}
                          className="flex-1 sm:flex-none px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-semibold"
                        >
                          Save
                        </button>
                        <button
                          onClick={cancelEditing}
                          className="flex-1 sm:flex-none px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors text-sm font-semibold"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    // View Mode
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={task.status === 'completed'}
                        onChange={() => toggleComplete(task.id)}
                        className="w-5 h-5 sm:w-6 sm:h-6 text-blue-600 rounded-md focus:ring-2 focus:ring-blue-500 cursor-pointer flex-shrink-0"
                      />
                      <span className={`flex-1 text-sm sm:text-base ${
                        task.status === 'completed' 
                          ? 'line-through text-gray-400' 
                          : 'text-gray-800'
                      }`}>
                        {task.name}
                      </span>
                      <div className="flex gap-2 flex-shrink-0">
<button
onClick={() => startEditing(task)}
className="px-3 py-1.5 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors text-sm font-semibold"
>
Edit
</button>
<button
onClick={() => deleteTask(task.id)}
className="px-3 py-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors text-sm font-semibold"
>
Delete
</button>
</div>
</div>
)}
</li>
))}
</ul>
)}
</div>
 {/* Footer */}
    <div className="mt-8 text-center text-gray-500 text-sm">
      <p>Thank You</p>
    </div>
  </div>
</div>
)
} 
export default App