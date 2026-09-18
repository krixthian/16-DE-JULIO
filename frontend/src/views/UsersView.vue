<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import api from '../services/api'

const router = useRouter()
const userStore = useUserStore()
const users = ref([])
const isLoading = ref(true)
const saving = ref(false)
const notice = ref('')
const formError = ref('')
const resending = ref(null)

// Redirigir si no está logueado o no es Admin
onMounted(async () => {
  if (!userStore.token) {
    const token = localStorage.getItem('token')
    if (!token) return router.push('/login')
    
    try {
      const res = await api.get('/auth/me', { headers: { Authorization: `Bearer ${token}` }})
      userStore.login(res.data, token)
    } catch (e) {
      localStorage.removeItem('token')
      return router.push('/login')
    }
  }
  
  if (userStore.user?.rol !== 'Admin') {
    // Si no es admin, no debería estar aquí
    alert('Acceso denegado: Solo administradores pueden gestionar usuarios.')
    router.push('/')
    return
  }

  fetchUsers()
})

const fetchUsers = async () => {
  isLoading.value = true
  try {
    const res = await api.get('/users/', {
      headers: { Authorization: `Bearer ${userStore.token}` }
    })
    users.value = res.data
  } catch (error) {
    console.error("Error al cargar usuarios", error)
  } finally {
    isLoading.value = false
  }
}

// Variables para el Modal
const showModal = ref(false)
const isEditing = ref(false)
const formUser = ref({
  id: null, nombre: '', apellido: '', email: '', rol: 'Docente', password: ''
})

const openModal = (user = null) => {
  if (user) {
    isEditing.value = true
    formUser.value = { ...user, password: '' } // La contraseña no se muestra
  } else {
    isEditing.value = false
    formUser.value = { id: null, nombre: '', apellido: '', email: '', rol: 'Docente', password: '' }
  }
  formError.value = ''
  showModal.value = true
}

const saveUser = async () => {
  if (saving.value) return
  saving.value = true
  formError.value = ''
  notice.value = ''
  try {
    const payload = { ...formUser.value }
    delete payload.id
    if (!payload.password || payload.rol === 'Docente' || payload.requiere_cambio_password || (isEditing.value && users.value.find(u => u.id === formUser.value.id)?.rol === 'Docente')) delete payload.password

    const config = { headers: { Authorization: `Bearer ${userStore.token}` } }

    if (isEditing.value) {
      await api.put(`/users/${formUser.value.id}`, payload, config)
    } else {
      await api.post('/users/', payload, { ...config, timeout: 60000 })
      notice.value = payload.rol === 'Docente' ? 'Docente registrado. El servidor de correo aceptó el envío de su contraseña temporal; pídele revisar también la carpeta de spam.' : 'Usuario registrado.'
    }
    showModal.value = false
    fetchUsers()
  } catch (error) {
    const detail = error.response?.data?.detail
    formError.value = typeof detail === 'string' ? detail : 'No se pudo confirmar el registro. Revisa la lista de usuarios antes de reintentar.'
  } finally { saving.value = false }
}

const resend = async (user) => {
  if (resending.value) return
  resending.value = user.id
  notice.value = ''
  try {
    const { data } = await api.post(`/users/${user.id}/resend-temporary-password`, {}, { timeout: 60000 })
    notice.value = data.message
  } catch (e) { notice.value = e.response?.data?.detail || 'No se pudo confirmar el envío. Recarga la lista e inténtalo de nuevo.' }
  finally { resending.value = null }
}

const deleteUser = async (id) => {
  if (confirm("¿Estás seguro de que deseas desactivar este usuario?")) {
    try {
      await api.delete(`/users/${id}`, {
        headers: { Authorization: `Bearer ${userStore.token}` }
      })
      fetchUsers()
    } catch (error) {
      console.error(error)
    }
  }
}
</script>

<template>
  <div class="p-8 max-w-7xl mx-auto transition-colors duration-300">
    
    <div class="flex justify-between items-center mb-8">
      <div>
        <h1 class="text-3xl font-extrabold text-gray-900 dark:text-white tracking-tight">Gestión de Usuarios</h1>
        <p class="text-gray-500 dark:text-slate-400 mt-1">Administra los accesos de docentes y directivos del sistema.</p>
      </div>
      <button @click="openModal()" class="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-xl font-medium shadow-md shadow-blue-500/30 transition-all flex items-center">
        <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
        Nuevo Usuario
      </button>
    </div>

    <p v-if="notice" role="status" class="mb-4 p-4 rounded-lg bg-blue-50 text-blue-900">{{ notice }}</p>
    <!-- Tabla -->
    <div class="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-gray-100 dark:border-slate-700 overflow-hidden transition-colors">
      <div v-if="isLoading" class="p-12 text-center text-gray-500 dark:text-slate-400">Cargando usuarios...</div>
      <table v-else class="w-full whitespace-nowrap">
        <thead class="bg-gray-50/50 dark:bg-slate-900/50 border-b border-gray-100 dark:border-slate-700 text-left">
          <tr>
            <th class="px-6 py-4 text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">Nombre Completo</th>
            <th class="px-6 py-4 text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">Correo Electrónico</th>
            <th class="px-6 py-4 text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">Rol</th>
            <th class="px-6 py-4 text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider">Estado</th>
            <th class="px-6 py-4 text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase tracking-wider text-right">Acciones</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-slate-700">
          <tr v-for="user in users" :key="user.id" class="hover:bg-gray-50/50 dark:hover:bg-slate-700/50 transition-colors">
            <td class="px-6 py-4">
              <div class="flex items-center">
                <div class="h-10 w-10 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-blue-700 dark:text-blue-400 font-bold">
                  {{ user.nombre.charAt(0) }}{{ user.apellido.charAt(0) }}
                </div>
                <div class="ml-4">
                  <div class="text-sm font-medium text-gray-900 dark:text-white">{{ user.nombre }} {{ user.apellido }}</div>
                </div>
              </div>
            </td>
            <td class="px-6 py-4 text-sm text-gray-600 dark:text-slate-300">{{ user.email }}</td>
            <td class="px-6 py-4">
              <span class="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full"
                    :class="{'bg-purple-100 text-purple-800': user.rol === 'Admin', 'bg-blue-100 text-blue-800': user.rol === 'Docente', 'bg-emerald-100 text-emerald-800': user.rol === 'Director'}">
                {{ user.rol }}
              </span>
            </td>
            <td class="px-6 py-4">
              <span v-if="user.activo" class="flex items-center text-sm text-green-600">
                <span class="h-2.5 w-2.5 rounded-full bg-green-500 mr-2"></span> Activo
              </span>
              <span v-else class="flex items-center text-sm text-red-600">
                <span class="h-2.5 w-2.5 rounded-full bg-red-500 mr-2"></span> Inactivo
              </span>
            </td>
            <td class="px-6 py-4 text-right text-sm font-medium">
              <button v-if="user.activo && user.requiere_cambio_password" @click="resend(user)" :disabled="resending !== null" class="text-blue-600 mr-4 disabled:opacity-50">{{ resending === user.id ? 'Enviando…' : 'Reenviar acceso temporal' }}</button>
              <button @click="openModal(user)" class="text-indigo-600 hover:text-indigo-900 mr-4">Editar</button>
              <button @click="deleteUser(user.id)" class="text-red-600 hover:text-red-900">Desactivar</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal Formulario (Simplificado para el ejemplo) -->
    <div v-if="showModal" class="fixed inset-0 bg-gray-900/50 dark:bg-slate-900/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div class="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl border border-transparent dark:border-slate-700 transition-colors">
        <h2 class="text-xl font-bold text-gray-900 dark:text-white mb-6">{{ isEditing ? 'Editar Usuario' : 'Nuevo Usuario' }}</h2>
        <form @submit.prevent="saveUser" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Nombre</label>
              <input v-model="formUser.nombre" type="text" required class="w-full px-4 py-2 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Apellido</label>
              <input v-model="formUser.apellido" type="text" required class="w-full px-4 py-2 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Correo Electrónico</label>
            <input v-model="formUser.email" type="email" required class="w-full px-4 py-2 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Rol</label>
            <select v-model="formUser.rol" required class="w-full px-4 py-2 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
              <option value="Docente">Docente</option>
              <option value="Director">Director</option>
              <option value="Admin">Administrador</option>
            </select>
          </div>
          <p v-if="!isEditing && formUser.rol === 'Docente'" class="text-sm p-3 rounded-lg bg-blue-50 text-blue-900">Se enviará una contraseña temporal al correo indicado. Vence en 24 horas y deberá cambiarse al ingresar.</p>
          <div v-if="formUser.rol !== 'Docente' && !formUser.requiere_cambio_password && (!isEditing || users.find(u => u.id === formUser.id)?.rol !== 'Docente')">
            <label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Contraseña <span v-if="isEditing" class="text-xs text-gray-400 dark:text-slate-500 font-normal">(Opcional si no cambia)</span></label>
            <input v-model="formUser.password" type="password" :required="!isEditing" class="w-full px-4 py-2 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-gray-900 dark:text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          </div>
          
          <p v-if="formError" role="alert" class="text-sm text-red-600">{{ formError }}</p>
          <div class="mt-8 flex justify-end space-x-3">
            <button type="button" :disabled="saving" @click="showModal = false" class="px-5 py-2 text-gray-600 dark:text-slate-300 bg-gray-100 dark:bg-slate-700 hover:bg-gray-200 dark:hover:bg-slate-600 rounded-xl font-medium transition-colors">Cancelar</button>
            <button type="submit" :disabled="saving" class="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium shadow-md shadow-blue-500/30 transition-all">{{ saving ? 'Guardando…' : 'Guardar' }}</button>
          </div>
        </form>
      </div>
    </div>
    
  </div>
</template>
