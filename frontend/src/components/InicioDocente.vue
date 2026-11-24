<script setup>
import { computed, onMounted, ref } from 'vue'
import { etiquetaCodigo } from '../utils/estudiante'
import api from '../services/api'
import PerfilRiesgo from './PerfilRiesgo.vue'

const data = ref(null), error = ref('')
const alertas = computed(() => data.value?.alertas || [])
const cuenta = n => alertas.value.filter(a => a.nivel === n).length
const primero = computed(() => alertas.value.slice(0, 5))
const tarjetas = computed(() => data.value ? [
  { l: 'Mis estudiantes', n: data.value.estudiantes_con_registro ?? 0, d: `${data.value.mis_cursos} ${data.value.mis_cursos === 1 ? 'curso' : 'cursos'}` },
  { l: 'Urgente', n: cuenta('URGENTE'), d: `${data.value.racha_alerta} o más faltas seguidas`, c: 'text-red-700 dark:text-red-400', p: 'bg-red-700' },
  { l: 'Rojo', n: cuenta('ROJO'), d: 'Atender pronto', c: 'text-red-600', p: 'bg-red-500' },
  { l: 'Amarillo', n: cuenta('AMARILLO'), d: 'Observar', c: 'text-amber-600', p: 'bg-amber-400' },
  { l: 'Verde', n: (data.value.estudiantes_con_registro ?? 0) - alertas.value.length, d: 'Sin alerta', c: 'text-emerald-600', p: 'bg-emerald-500' }] : [])
const NIVEL = { URGENTE: ['Urgente', 'bg-red-700 text-white'], ROJO: ['Rojo', 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'],
  AMARILLO: ['Amarillo', 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'] }
const accion = a => a.nivel === 'URGENTE' ? `${a.faltas_seguidas} faltas seguidas: avisa hoy a Dirección` : a.por_materia || ''
const fecha = f => f ? f.split('-').reverse().join('/') : ''
const TAREAS = [['/asistencia', '✓', 'Asistencia diaria', 'Pasar lista'], ['/asistencia-materia', '%', 'Asistencia por materia', 'Por hora y citaciones'],
  ['/calificaciones', 'N', 'Calificaciones', 'Registrar notas'], ['/mis-notas', 'D', 'Notas desglosadas', 'Por dimensión y actividad'], ['/tareas', 'T', 'Tareas', 'Entregas y pendientes']]
async function load() {
  error.value = ''
  try { data.value = (await api.get('/docente/alertas', { timeout: 30000 })).data }
  catch (e) { error.value = e.response?.data?.detail || 'No se pudieron cargar tus alertas.' }
}
onMounted(load)
</script>
<template>
 <div class="mt-6 space-y-6">
  <nav aria-label="Accesos rápidos" class="grid sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
   <RouterLink v-for="([to, icono, l, d], i) in TAREAS" :key="to" :to="to" class="flex items-center gap-3 rounded-xl border p-4 hover:shadow-md" :class="i ? 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-blue-500' : 'border-blue-600 bg-blue-600 text-white hover:bg-blue-700'">
    <span class="grid place-items-center h-10 w-10 shrink-0 rounded-lg font-bold" :class="i ? 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300' : 'bg-white/20'" aria-hidden="true">{{ icono }}</span>
    <span><span class="block font-semibold text-sm">{{ l }}</span><span class="block text-xs" :class="i ? 'text-slate-500' : 'text-blue-100'">{{ d }}</span></span>
   </RouterLink>
  </nav>

  <div v-if="error" role="alert" class="bg-red-50 text-red-800 rounded-xl p-4">{{ error }} <button class="underline" @click="load">Reintentar</button></div>
  <p v-else-if="!data" class="text-slate-500">Calculando las alertas de tus cursos…</p>
  <template v-else>
   <section>
    <div class="flex flex-wrap items-baseline gap-2"><h2 class="text-lg font-semibold">Cómo van mis estudiantes</h2><span class="text-sm text-slate-500">Gestión {{ data.gestion }} al {{ fecha(data.fecha) }}</span>
     <span v-if="alertas.some(a => a.origen === 'SIMULADO')" class="px-2 py-0.5 rounded-full text-xs bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200">Datos simulados</span></div>
    <div class="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 mt-3">
     <div v-for="t in tarjetas" :key="t.l" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4">
      <p class="text-sm text-slate-500 flex items-center gap-1.5"><span v-if="t.p" class="h-2.5 w-2.5 rounded-full" :class="t.p" aria-hidden="true"></span>{{ t.l }}</p>
      <p class="text-3xl font-bold mt-1" :class="t.c">{{ t.n }}</p><p class="text-xs text-slate-500 mt-1">{{ t.d }}</p>
     </div>
    </div>
   </section>
   <section class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
    <div class="flex items-center justify-between gap-3 p-5 pb-3"><h2 class="text-lg font-semibold">A quién atender primero</h2><RouterLink v-if="alertas.length" to="/mis-alertas" class="text-sm font-semibold text-blue-600 dark:text-blue-400">Ver los {{ alertas.length }} →</RouterLink></div>
    <p v-if="!alertas.length" class="px-5 pb-5 text-slate-500">{{ data.motivo || 'Ningún estudiante de tus cursos tiene alerta.' }}</p>
    <ul v-else class="divide-y divide-slate-100 dark:divide-slate-700">
     <li v-for="a in primero" :key="a.matricula_id"><RouterLink to="/mis-alertas" class="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/40">
      <span class="w-20"><span class="px-2 py-1 rounded-full text-xs font-semibold" :class="NIVEL[a.nivel][1]">{{ NIVEL[a.nivel][0] }}</span></span>
      <span class="font-medium min-w-48">{{ etiquetaCodigo(a.estudiante) }} <span class="text-sm font-normal text-slate-500">· {{ a.curso }}</span></span>
      <PerfilRiesgo solo-alertas :colores="a.colores" />
      <span class="text-sm text-slate-500">{{ accion(a) }}</span>
     </RouterLink></li>
    </ul>
   </section>
   <p class="text-xs text-slate-500">El color ordena a quién mirar primero; no significa que el estudiante vaya a abandonar.</p>
  </template>
 </div>
</template>
