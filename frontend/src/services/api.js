import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000', // URL base del backend FastAPI
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})

// Interceptores para añadir el token JWT (implementación futura)
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, error => {
  return Promise.reject(error)
})

export default api
