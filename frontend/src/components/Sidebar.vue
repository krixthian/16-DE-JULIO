<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const isDark = ref(false)

onMounted(() => {
  if (localStorage.getItem('theme') === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
})

const toggleDarkMode = () => {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }
}


const isLoggedIn = computed(() => !!userStore.token)
const userRol = computed(() => userStore.user?.rol)
const userName = computed(() => userStore.user?.nombre)
const isExpanded = ref(true)

const toggleSidebar = () => {
  isExpanded.value = !isExpanded.value
}

const logout = () => {
  localStorage.removeItem('token')
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <aside v-if="isLoggedIn" :class="isExpanded ? 'w-64' : 'w-20'" class="bg-[#0f172a] text-white transition-all duration-300 flex flex-col min-h-screen shadow-2xl relative border-r border-slate-800">
    <!-- Header Sidebar -->
    <div class="h-16 flex items-center justify-between px-4 border-b border-slate-800 bg-slate-900/50">
      <div v-if="isExpanded" class="flex items-center space-x-2 overflow-hidden">
        <svg class="w-8 h-8 text-blue-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
        <span class="font-bold text-sm tracking-widest truncate">UE 16 DE JULIO</span>
      </div>
      <button @click="toggleSidebar" class="p-2 rounded-lg hover:bg-slate-800 focus:outline-none transition-colors ml-auto text-slate-400 hover:text-white">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
      </button>
    </div>

    <!-- User Info -->
    <div v-if="isExpanded" class="px-6 py-8 border-b border-slate-800 text-center bg-gradient-to-b from-slate-900/50 to-transparent">
      <div class="w-20 h-20 rounded-full bg-blue-600 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-900/50 ring-4 ring-slate-800">
        <span class="text-3xl font-bold text-white">{{ userName?.charAt(0) || 'U' }}</span>
      </div>
      <p class="text-base font-semibold text-white">{{ userName }}</p>
      <p class="text-xs text-blue-400 mt-1 uppercase tracking-wider font-bold">{{ userRol }}</p>
    </div>

    <!-- Navegación -->
    <nav class="flex-1 px-4 py-6 space-y-3">
      <router-link to="/" class="flex items-center px-3 py-3.5 rounded-xl transition-all duration-200 group" active-class="bg-blue-600 text-white shadow-lg shadow-blue-900/50" :class="[isExpanded ? 'justify-start' : 'justify-center', $route.path === '/' ? '' : 'hover:bg-slate-800 text-slate-300']">
        <svg class="w-6 h-6 flex-shrink-0" :class="$route.path === '/' ? 'text-white' : 'text-slate-400 group-hover:text-blue-400 transition-colors'" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>
        <span v-if="isExpanded" class="ml-4 font-medium">Panel de Control</span>
      </router-link>

      <router-link v-if="userRol === 'Admin'" to="/users" class="flex items-center px-3 py-3.5 rounded-xl transition-all duration-200 group" active-class="bg-indigo-600 text-white shadow-lg shadow-indigo-900/50" :class="[isExpanded ? 'justify-start' : 'justify-center', $route.path === '/users' ? '' : 'hover:bg-slate-800 text-slate-300']">
        <svg class="w-6 h-6 flex-shrink-0" :class="$route.path === '/users' ? 'text-white' : 'text-slate-400 group-hover:text-indigo-400 transition-colors'" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
        <span v-if="isExpanded" class="ml-4 font-medium">Gestión Usuarios</span>
      </router-link>
      <div v-if="['Admin', 'Director'].includes(userRol)" class="pt-3 space-y-2">
        <p v-if="isExpanded" class="px-3 text-xs uppercase tracking-wider text-slate-500 mb-3">Administración escolar</p>
        <router-link v-for="item in [{path:'gestiones',label:'Gestiones',short:'G'},{path:'cursos',label:'Cursos',short:'C'},{path:'estudiantes',label:'Estudiantes',short:'E'},{path:'matriculas',label:'Matrículas',short:'M'},{path:'materias',label:'Materias',short:'T'},{path:'asignaciones',label:'Asignaciones',short:'A'}]" :key="item.path" :to="`/escolar/${item.path}`" :title="item.label" class="flex items-center px-3 py-3 rounded-xl text-slate-300 hover:bg-slate-800" active-class="bg-blue-600 !text-white" :class="isExpanded ? '' : 'justify-center'">
          <span class="w-6 h-6 border border-current rounded text-center text-sm leading-6 shrink-0" aria-hidden="true">{{ item.short }}</span><span v-if="isExpanded" class="ml-4 font-medium">{{ item.label }}</span><span v-else class="sr-only">{{ item.label }}</span>
        </router-link>
      </div>
      <router-link v-if="['Admin','Director','Docente'].includes(userRol)" to="/asistencia" title="Asistencia diaria" class="flex items-center px-3 py-3 rounded-xl text-slate-300 hover:bg-slate-800" active-class="bg-blue-600 !text-white" :class="isExpanded ? '' : 'justify-center'"><span class="w-6 h-6 border border-current rounded text-center text-sm leading-6 shrink-0" aria-hidden="true">✓</span><span v-if="isExpanded" class="ml-4 font-medium">Asistencia diaria</span><span v-else class="sr-only">Asistencia diaria</span></router-link>
      <router-link v-if="['Admin','Director','Docente'].includes(userRol)" to="/calificaciones" title="Calificaciones" class="flex items-center px-3 py-3 rounded-xl text-slate-300 hover:bg-slate-800" active-class="bg-blue-600 !text-white" :class="isExpanded ? '' : 'justify-center'"><span class="w-6 h-6 border border-current rounded text-center text-sm leading-6 shrink-0" aria-hidden="true">N</span><span v-if="isExpanded" class="ml-4 font-medium">Calificaciones</span><span v-else class="sr-only">Calificaciones</span></router-link>
    </nav>

    <!-- Ajustes y Logout -->
    <div class="p-4 border-t border-slate-800 bg-slate-900/50">
      
      <!-- Dark Mode Toggle -->
      <button @click="toggleDarkMode" class="w-full flex items-center px-3 py-3 mb-2 rounded-xl text-slate-400 hover:bg-slate-800 hover:text-white transition-all group" :class="isExpanded ? 'justify-start' : 'justify-center'" title="Cambiar Tema">
        <svg v-if="!isDark" class="w-6 h-6 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path></svg>
        <svg v-else class="w-6 h-6 flex-shrink-0 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
        <span v-if="isExpanded" class="ml-4 font-medium">{{ isDark ? 'Modo Claro' : 'Modo Oscuro' }}</span>
      </button>

      <!-- Logout -->
      <button @click="logout" class="w-full flex items-center px-3 py-3 rounded-xl text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-all group" :class="isExpanded ? 'justify-start' : 'justify-center'" title="Cerrar Sesión">
        <svg class="w-6 h-6 flex-shrink-0 group-hover:rotate-180 transition-transform duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
        <span v-if="isExpanded" class="ml-4 font-medium">Cerrar Sesión</span>
      </button>
    </div>
  </aside>
</template>
