<script setup>
import { ref, computed, onMounted } from 'vue'
import { etiquetaCodigo } from '../utils/estudiante'
import { useUserStore } from '../stores/user'
import api from '../services/api'
import AyudaPantalla from '../components/AyudaPantalla.vue'
import PerfilRiesgo from '../components/PerfilRiesgo.vue'

const store = useUserStore()
const data = ref(null), busy = ref(false), error = ref(''), year = ref(''), day = ref('')
const message = e => e.response?.data?.detail || 'No se pudo conectar con el servidor.'
const inmediatas = computed(() => (data.value?.alertas || []).filter(a => a.alerta_inmediata))
const otras = computed(() => (data.value?.alertas || []).filter(a => !a.alerta_inmediata))
const nivel = n => n === 'ROJO' ? ['Rojo · atender pronto', 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200']
  : ['Amarillo · observar', 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200']

async function load() {
  busy.value = true; error.value = ''
  try {
    const params = {}
    if (year.value) params.gestion = year.value
    if (day.value) params.fecha = day.value
    data.value = (await api.get('/docente/alertas', { params, timeout: 30000 })).data
    year.value = data.value.gestion; day.value = data.value.fecha
  } catch (e) { error.value = message(e) } finally { busy.value = false }
}
function changeYear() { day.value = ''; load() }
onMounted(load)
</script>

<template>
 <section class="p-4 md:p-8 max-w-6xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Alerta temprana</p>
  <h1 class="text-3xl font-bold">Mis estudiantes con alerta</h1>
  <p class="mt-2 text-slate-500 dark:text-slate-400 max-w-3xl">
   {{ store.user?.rol === 'Docente' ? 'Estudiantes de tus cursos que necesitan atención.' : 'Vista previa de lo que ve cada docente (aquí, todos los cursos).' }}

  </p>

  <div class="flex flex-wrap items-end gap-3 mt-6">
   <label class="text-sm font-medium">Gestión<input v-model.number="year" type="number" min="2000" max="2100" @change="changeYear" class="block mt-1 w-28 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"></label>
   <label class="text-sm font-medium">Fecha<input v-model="day" type="date" @change="load" class="block mt-1 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"></label>
   <span v-if="busy" class="text-sm text-slate-500 pb-2">Calculando…</span>
   <span v-else-if="data" class="text-sm text-slate-500 pb-2">{{ data.mis_cursos }} curso(s) · {{ data.total }} estudiante(s) con alerta</span>
  </div>
  <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }}</div>

  <template v-if="data">
   <AyudaPantalla class="mt-4"><p>{{ data.nota }}</p><p>El color ordena a quién mirar primero; no significa que el estudiante vaya a abandonar. Solo se muestran las dimensiones con problema.</p></AyudaPantalla>

   <p v-if="!data.alertas.length" class="mt-6 rounded-xl border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-200 p-6 text-center">
    {{ data.motivo || 'Ningún estudiante de tus cursos tiene alerta a esta fecha.' }}
   </p>

   <section v-if="inmediatas.length" class="mt-8">
    <h2 class="font-semibold text-lg flex items-center gap-2"><span class="inline-block h-3 w-3 rounded-full bg-red-600" aria-hidden="true"></span>Alerta inmediata · {{ data.racha_alerta }} o más faltas seguidas</h2>
    <div class="grid md:grid-cols-2 gap-4 mt-3">
     <article v-for="a in inmediatas" :key="a.matricula_id" class="rounded-xl border-2 border-red-300 dark:border-red-800 bg-white dark:bg-slate-800 p-5">
      <div class="flex items-start justify-between gap-3">
       <div><p class="font-semibold text-lg">{{ etiquetaCodigo(a.estudiante) }}</p><p class="text-sm text-slate-500">{{ a.curso }}</p></div>
       <span class="px-3 py-1 rounded-full text-xs font-semibold bg-red-600 text-white whitespace-nowrap">{{ a.faltas_seguidas }} faltas seguidas</span>
      </div>
      <p class="mt-3 text-sm">Última asistencia: <strong>{{ a.ultima_asistencia || 'sin asistencia registrada' }}</strong></p>
      <PerfilRiesgo class="mt-3" solo-alertas :colores="a.colores" /><p v-if="a.por_materia" class="mt-1 text-xs text-slate-500">{{ a.por_materia }}</p>
      <p class="mt-4 text-sm rounded-lg bg-red-50 dark:bg-red-950/40 text-red-900 dark:text-red-200 p-3">Avisa hoy a Dirección u Orientación.</p>
     </article>
    </div>
   </section>

   <section v-if="otras.length" class="mt-8">
    <h2 class="font-semibold text-lg">Para observar</h2>
    <div class="mt-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
     <table class="w-full text-sm"><thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr><th class="px-4 py-2.5">Estudiante</th><th class="px-4 py-2.5">Curso</th><th class="px-4 py-2.5">Prioridad</th><th class="px-4 py-2.5">Motivo</th><th class="px-4 py-2.5">Faltas seguidas</th></tr></thead>
      <tbody><tr v-for="a in otras" :key="a.matricula_id" class="border-t border-slate-100 dark:border-slate-700 align-top">
       <td class="px-4 py-2.5 font-medium whitespace-nowrap">{{ etiquetaCodigo(a.estudiante) }}</td>
       <td class="px-4 py-2.5 whitespace-nowrap">{{ a.curso }}</td>
       <td class="px-4 py-2.5 whitespace-nowrap"><span class="px-2 py-1 rounded-full text-xs font-semibold" :class="nivel(a.nivel)[1]">{{ nivel(a.nivel)[0] }}</span><span v-if="a.notas_y_asistencia" class="block mt-1 w-fit px-2 py-0.5 rounded-full border border-red-300 dark:border-red-800 text-[11px] text-red-800 dark:text-red-200">Notas y asistencia</span></td>
       <td class="px-4 py-2.5"><PerfilRiesgo solo-alertas :colores="a.colores" /><p v-if="a.por_materia" class="mt-1 text-xs text-slate-500">{{ a.por_materia }}</p></td>
       <td class="px-4 py-2.5 tabular-nums">{{ a.faltas_seguidas }}</td>
      </tr></tbody></table>
    </div>
   </section>

   <div class="mt-8 flex flex-wrap gap-3 text-sm">
    <RouterLink to="/asistencia" class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700">Registrar asistencia de hoy</RouterLink>
    <RouterLink to="/asistencia-materia" class="px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 hover:border-blue-500">Citar a la familia por mi materia</RouterLink>
   </div>
  </template>
 </section>
</template>
