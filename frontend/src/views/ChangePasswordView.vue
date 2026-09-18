<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import api from '../services/api'
const router = useRouter()
const store = useUserStore()
const current = ref(''), password = ref(''), confirmation = ref(''), error = ref(''), busy = ref(false)
const logout = () => { store.logout(); router.replace('/login') }
async function save() {
  error.value = ''
  if (password.value !== confirmation.value) { error.value = 'Las contraseñas no coinciden.'; return }
  if (password.value === current.value) { error.value = 'Elige una contraseña diferente de la temporal.'; return }
  busy.value = true
  try {
    const { data } = await api.post('/auth/change-password', { current_password: current.value, new_password: password.value })
    store.login({ ...store.user, requiere_cambio_password: false }, data.access_token)
    current.value = password.value = confirmation.value = ''
    await router.replace('/')
  } catch (e) {
    const detail = e.response?.data?.detail
    error.value = typeof detail === 'string' ? detail : 'No se pudo cambiar la contraseña. Usa al menos 12 caracteres y como máximo 72 bytes.'
  } finally { busy.value = false }
}
</script>
<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 to-indigo-700 px-4">
    <form @submit.prevent="save" class="w-full max-w-md bg-white dark:bg-slate-800 rounded-2xl p-8 shadow-xl space-y-5 text-gray-900 dark:text-white">
      <h1 class="text-2xl font-bold">Establece tu contraseña</h1>
      <p class="text-sm text-gray-600 dark:text-slate-300">Antes de continuar, reemplaza la contraseña temporal que recibiste por correo.</p>
      <div><label for="current" class="block mb-1">Contraseña temporal</label><input id="current" v-model="current" type="password" autocomplete="current-password" required class="w-full border rounded-lg p-3 dark:bg-slate-700" /></div>
      <div><label for="new" class="block mb-1">Nueva contraseña</label><input id="new" v-model="password" type="password" autocomplete="new-password" minlength="12" maxlength="72" required class="w-full border rounded-lg p-3 dark:bg-slate-700" /><p class="text-sm mt-1 text-gray-500 dark:text-slate-300">Utiliza al menos 12 caracteres.</p></div>
      <div><label for="confirm" class="block mb-1">Repite la nueva contraseña</label><input id="confirm" v-model="confirmation" type="password" autocomplete="new-password" required class="w-full border rounded-lg p-3 dark:bg-slate-700" /></div>
      <p v-if="error" role="alert" class="text-red-600">{{ error }}</p>
      <button :disabled="busy" class="w-full bg-blue-600 text-white p-3 rounded-lg disabled:opacity-50">{{ busy ? 'Guardando…' : 'Guardar y continuar' }}</button>
      <button type="button" @click="logout" :disabled="busy" class="w-full text-sm">Volver al inicio de sesión</button>
    </form>
  </div>
</template>
