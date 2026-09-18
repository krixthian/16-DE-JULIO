<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const isLoggedIn = computed(() => !!userStore.token)
const userRol = computed(() => userStore.user?.rol)
const userName = computed(() => userStore.user?.nombre)

const logout = () => {
  localStorage.removeItem('token')
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <nav class="bg-blue-900 shadow-lg border-b border-blue-800">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16">
        <div class="flex items-center">
          <router-link to="/" class="flex items-center space-x-3 text-white hover:text-blue-200 transition-colors">
            <svg class="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
            <span class="font-bold text-xl tracking-wide">UNIDAD EDUCATIVA 16 DE JULIO</span>
          </router-link>
        </div>
        
        <div class="flex items-center space-x-3">
          <router-link v-if="isLoggedIn" to="/" class="bg-blue-800/80 hover:bg-blue-700 text-white px-4 py-2 rounded-xl text-sm font-bold shadow-sm transition-all border border-blue-700 hover:border-blue-500 flex items-center">
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
            Panel de Control
          </router-link>

          <router-link v-if="isLoggedIn && userRol === 'Admin'" to="/users" class="bg-indigo-600/90 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-sm font-bold shadow-md shadow-indigo-500/20 transition-all border border-indigo-500 hover:border-indigo-400 flex items-center">
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
            Gestión de Usuarios
          </router-link>
          
          <div v-if="isLoggedIn" class="flex items-center space-x-4 ml-4 pl-4 border-l border-blue-700">
            <span class="text-sm text-blue-200">Hola, <span class="text-white font-semibold">{{ userName }}</span></span>
            <button @click="logout" class="bg-red-500/90 hover:bg-red-500 text-white px-4 py-2 rounded-lg text-sm font-medium shadow transition-colors">
              Salir
            </button>
          </div>
          
          <div v-else>
            <router-link to="/login" class="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 rounded-lg text-sm font-medium shadow-md transition-colors">
              Iniciar Sesión
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>
