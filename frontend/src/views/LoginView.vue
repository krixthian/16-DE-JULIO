<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import api from '../services/api'

const router = useRouter()
const userStore = useUserStore()

const email = ref('')
const password = ref('')
const errorMsg = ref('')
const isLoading = ref(false)

const handleLogin = async () => {
  isLoading.value = true
  errorMsg.value = ''
  
  try {
    const formData = new URLSearchParams()
    formData.append('username', email.value)
    formData.append('password', password.value)

    const response = await api.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    })
    
    const token = response.data.access_token
    localStorage.setItem('token', token)
    
    // Obtener datos del usuario
    const userResponse = await api.get('/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    })
    
    userStore.login(userResponse.data, token)
    router.push('/')
  } catch (error) {
    if (error.response && error.response.data) {
      errorMsg.value = error.response.data.detail || 'Error de autenticación'
    } else {
      errorMsg.value = 'Error al conectar con el servidor'
    }
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 via-indigo-800 to-blue-600 px-4">
    <div class="max-w-md w-full bg-white/10 backdrop-blur-lg rounded-3xl shadow-2xl overflow-hidden border border-white/20 p-8 transform transition-all hover:scale-105 duration-300">
      
      <div class="text-center mb-10">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-500/30 mb-4 shadow-inner">
          <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
        </div>
        <h2 class="text-3xl font-extrabold text-white tracking-tight">UNIDAD EDUCATIVA</h2>
        <h2 class="text-3xl font-extrabold text-white tracking-tight">"16 DE JULIO"</h2>

      </div>

      <form @submit.prevent="handleLogin" class="space-y-6">
        <div>
          <label for="email" class="block text-sm font-medium text-blue-100 mb-1">Correo Electrónico</label>
          <input id="email" v-model="email" type="email" required 
                 class="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all"
                 placeholder="docente@16dejulio.edu.bo" />
        </div>

        <div>
          <label for="password" class="block text-sm font-medium text-blue-100 mb-1">Contraseña</label>
          <input id="password" v-model="password" type="password" required 
                 class="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-blue-300/50 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all"
                 placeholder="••••••••" />
        </div>
        
        <div v-if="errorMsg" class="bg-red-500/20 border border-red-500/50 text-red-200 px-4 py-3 rounded-lg text-sm flex items-center">
          <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>
          {{ errorMsg }}
        </div>

        <button type="submit" :disabled="isLoading"
                class="w-full py-3 px-4 flex justify-center rounded-xl text-sm font-bold text-blue-900 bg-white hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-blue-800 focus:ring-white transition-all shadow-lg active:scale-95 disabled:opacity-70 disabled:cursor-not-allowed">
          <span v-if="isLoading">Verificando credenciales...</span>
          <span v-else>Iniciar Sesión</span>
        </button>
      </form>
    </div>
  </div>
</template>
