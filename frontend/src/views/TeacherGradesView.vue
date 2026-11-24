<script setup>
import { ref, computed, onMounted } from 'vue'
import { etiquetaCodigo } from '../utils/estudiante'
import api from '../services/api'

const contexto = ref({ asignaciones: [], gestiones: [] }), data = ref(null), busy = ref(false), error = ref('')
const gestion = ref(''), curso = ref(''), asignacion = ref(''), day = ref(''), abierto = ref(null)
const TIPOS = { PRUEBA: 'Pruebas', TRABAJO: 'Trabajos', PROYECTO: 'Proyectos', ORAL: 'Orales', OTRA: 'Otras' }
const message = e => e.response?.data?.detail || 'No se pudo conectar con el servidor.'
const num = v => v == null ? '—' : Number(v).toFixed(1).replace('.', ',').replace(',0', '')
const signo = v => v == null ? '—' : `${v > 0 ? '+' : ''}${num(v)}`
const deGestion = computed(() => contexto.value.asignaciones.filter(a => a.gestion_id === gestion.value))
const cursos = computed(() => [...new Map(deGestion.value.map(a => [a.curso_id, a.curso_nombre]))])
const materias = computed(() => deGestion.value.filter(a => a.curso_id === curso.value))
const gestiones = computed(() => contexto.value.gestiones.filter(g => contexto.value.asignaciones.some(a => a.gestion_id === g.id)))
const tipos = computed(() => Object.keys(TIPOS).filter(t => data.value?.actividades[t]))
const hayDetalle = computed(() => data.value && (data.value.total_actividades || data.value.total_tareas || data.value.dimensiones.length))
const ultimo = computed(() => Math.max(0, ...(data.value?.dimensiones || []).map(d => d.trimestre)))
const dims = computed(() => (data.value?.dimensiones || []).filter(d => d.trimestre === ultimo.value))

const lista = ref(null)
async function verActividades(e, d) {
  const clave = `${e.matricula_id}-${d.clave}`
  if (lista.value?.clave === clave) { lista.value = null; return }
  lista.value = { clave, actividades: null }
  try {
    const r = (await api.get('/docente/notas/actividades', { params: { asignacion_id: asignacion.value, matricula_id: e.matricula_id, trimestre: d.trimestre, dimension: d.dimension, fecha: day.value } })).data
    if (lista.value?.clave === clave) lista.value = { clave, ...r }
  } catch (x) { if (lista.value?.clave === clave) lista.value = { clave, error: message(x) } }
}
async function load() {
  if (!asignacion.value) { data.value = null; return }
  const pedido = asignacion.value
  busy.value = true; error.value = ''; abierto.value = null; lista.value = null
  try {
    const params = { asignacion_id: pedido }
    if (day.value) params.fecha = day.value
    const r = (await api.get('/docente/notas', { params, timeout: 30000 })).data
    if (pedido !== asignacion.value) return
    data.value = r; day.value = r.fecha
  } catch (e) { data.value = null; error.value = message(e) } finally { if (pedido === asignacion.value) busy.value = false }
}
function elegirGestion() { day.value = ''; curso.value = cursos.value[0]?.[0] || ''; elegirCurso() }
function elegirCurso() { asignacion.value = materias.value[0]?.id || ''; load() }
onMounted(async () => {
  try {
    contexto.value = (await api.get('/calificaciones/contexto')).data
    gestion.value = gestiones.value[0]?.id || ''
    elegirGestion()
  } catch (e) { error.value = message(e) }
})
</script>

<template>
 <section class="p-4 md:p-8 max-w-6xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Rendimiento</p>
  <h1 class="text-3xl font-bold">Notas desglosadas</h1>
  <p class="mt-2 text-slate-500 dark:text-slate-400 max-w-3xl">Pruebas, trabajos y tareas de cada estudiante en tu materia, comparados con su curso y con sus notas anteriores.</p>

  <div class="flex flex-wrap items-end gap-3 mt-6">
   <label class="text-sm font-medium">Gestión<select v-model="gestion" @change="elegirGestion" class="campo"><option v-for="g in gestiones" :key="g.id" :value="g.id">{{ g.anio }}</option></select></label>
   <label class="text-sm font-medium">Curso<select v-model="curso" @change="elegirCurso" class="campo"><option v-for="[id, nombre] in cursos" :key="id" :value="id">{{ nombre }}</option></select></label>
   <label class="text-sm font-medium">Materia<select v-model="asignacion" @change="load" class="campo max-w-[15rem]"><option v-for="a in materias" :key="a.id" :value="a.id">{{ a.materia_nombre }}</option></select></label>
   <label class="text-sm font-medium">Fecha<input v-model="day" type="date" @change="load" class="campo"></label>
   <span v-if="busy" class="text-sm text-slate-500 pb-2">Cargando…</span>
  </div>
  <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }}</div>
  <p v-if="!busy && !error && !asignacion" class="mt-6 text-slate-500">No tienes asignaciones en esta gestión.</p>

  <template v-if="data">
   <div class="mt-6 rounded-xl border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40 text-blue-900 dark:text-blue-100 p-4 text-sm">{{ data.nota }}</div>

   <div v-if="!hayDetalle" class="mt-6 rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-200 p-5 text-sm">
    <strong>Todavía no hay actividades registradas</strong> en {{ data.materia }}, {{ data.curso }}, hasta esta fecha.
    <template v-if="data.trimestres.length">Solo existe la nota de cierre de cada trimestre.</template>
    El desglose aparecerá a medida que se registren pruebas, trabajos y tareas con su fecha.
   </div>
   <p v-else class="mt-6 text-sm text-slate-500"><template v-if="dims.length">Nota de cada dimensión al trimestre {{ ultimo }}, sobre 100. </template>{{ data.total_actividades }} actividad(es) calificable(s) y {{ data.total_tareas }} tarea(s) vencida(s) hasta la fecha. Toca un estudiante para ver el detalle.</p>

   <div v-if="data.estudiantes.length" class="mt-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
    <table class="w-full text-sm">
     <thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr>
      <th class="px-4 py-2.5">Estudiante</th>
      <th v-for="d in dims" :key="d.clave" class="px-3 py-2.5 text-right">{{ d.dimension }} <span class="font-normal text-slate-500">T{{ d.trimestre }}</span></th>
      <th v-for="t in tipos" :key="t" class="px-3 py-2.5 text-right">{{ TIPOS[t] }}</th>
      <th v-if="data.total_actividades" class="px-3 py-2.5 text-right">Promedio</th>
      <th v-if="data.total_actividades" class="px-3 py-2.5 text-right">Cambio en {{ data.semanas }} sem.</th>
      <th v-if="data.total_tareas" class="px-3 py-2.5 text-right">Tareas sin entregar</th>
      <th v-for="k in data.trimestres" :key="k" class="px-3 py-2.5 text-right">Trimestre {{ k }}</th>
     </tr></thead>
     <tbody>
      <tr class="border-t border-slate-100 dark:border-slate-700 font-semibold bg-slate-50/60 dark:bg-slate-900/40">
       <td class="px-4 py-2.5">Promedio del curso</td>
       <td v-for="d in dims" :key="d.clave" class="celda">{{ num(data.curso_promedio.dimensiones[d.clave]) }}</td>
       <td v-for="t in tipos" :key="t" class="celda">{{ num(data.curso_promedio.por_tipo[t]) }}</td>
       <td v-if="data.total_actividades" class="celda">{{ num(data.curso_promedio.promedio) }}</td>
       <td v-if="data.total_actividades"></td>
       <td v-if="data.total_tareas"></td>
       <td v-for="k in data.trimestres" :key="k" class="celda">{{ num(data.curso_promedio.trimestres[k]) }}</td>
      </tr>
      <template v-for="e in data.estudiantes" :key="e.matricula_id">
       <tr class="border-t border-slate-100 dark:border-slate-700">
        <td class="px-4 py-2.5 font-medium whitespace-nowrap">
         <button v-if="hayDetalle" type="button" class="text-left hover:underline" :aria-expanded="abierto === e.matricula_id" @click="abierto = abierto === e.matricula_id ? null : e.matricula_id; lista = null">{{ etiquetaCodigo(e.estudiante) }}</button>
         <template v-else>{{ etiquetaCodigo(e.estudiante) }}</template>
         <span v-if="e.origen==='SIMULADO'" class="ml-1 text-xs text-slate-400">(simulado)</span>
        </td>
        <td v-for="d in dims" :key="d.clave" class="celda" :class="e.dimensiones[d.clave] != null && e.dimensiones[d.clave] < 51 ? 'bajo' : ''">{{ num(e.dimensiones[d.clave]) }}</td>
        <td v-for="t in tipos" :key="t" class="celda" :class="e.por_tipo[t] != null && e.por_tipo[t] < 51 ? 'bajo' : ''">{{ num(e.por_tipo[t]) }}</td>
        <td v-if="data.total_actividades" class="celda" :class="e.promedio != null && e.promedio < 51 ? 'bajo' : ''">{{ num(e.promedio) }}</td>
        <td v-if="data.total_actividades" class="celda">{{ signo(e.cambio) }}</td>
        <td v-if="data.total_tareas" class="celda">{{ e.tareas.entregadas + e.tareas.no_entregadas ? `${e.tareas.no_entregadas} de ${e.tareas.entregadas + e.tareas.no_entregadas}` : '—' }}</td>
        <td v-for="k in data.trimestres" :key="k" class="celda" :class="e.trimestres[k] != null && e.trimestres[k] < 51 ? 'bajo' : ''">{{ num(e.trimestres[k]) }}</td>
       </tr>
       <tr v-if="abierto === e.matricula_id"><td colspan="16" class="px-4 pb-4 text-sm text-slate-600 dark:text-slate-300">
        <ul class="rounded-lg bg-slate-50 dark:bg-slate-900 p-4 space-y-1">
         <li v-for="d in data.dimensiones" :key="d.clave">· {{ d.dimension }}, trimestre {{ d.trimestre }}: <strong>{{ num(e.dimensiones[d.clave]) }}</strong> (su curso: {{ num(data.curso_promedio.dimensiones[d.clave]) }})
          <button v-if="d.con_actividades" type="button" class="ml-2 underline text-blue-700 dark:text-blue-300" :aria-expanded="lista?.clave === `${e.matricula_id}-${d.clave}`" @click="verActividades(e, d)">{{ lista?.clave === `${e.matricula_id}-${d.clave}` ? 'Ocultar actividades' : 'Ver actividades' }}</button>
          <div v-if="lista?.clave === `${e.matricula_id}-${d.clave}`" class="my-2 ml-3 max-w-xl overflow-x-auto">
           <p v-if="lista.error" class="text-red-600">{{ lista.error }}</p>
           <p v-else-if="!lista.actividades">Cargando…</p>
           <table v-else class="w-full text-xs"><thead class="text-left text-slate-500"><tr><th class="py-1 pr-3">Actividad</th><th class="py-1 pr-3">Fecha</th><th class="py-1 pr-3 text-right">Nota</th><th class="py-1 text-right">Su curso</th></tr></thead>
            <tbody><tr v-for="x in lista.actividades" :key="x.id" class="border-t border-slate-200 dark:border-slate-700"><td class="py-1 pr-3 whitespace-normal">{{ x.titulo }}</td><td class="py-1 pr-3 whitespace-nowrap">{{ x.fecha || 'sin fecha propia' }}</td>
             <td class="py-1 pr-3 text-right whitespace-nowrap" :class="x.puntaje != null && x.puntaje / x.maximo < .51 ? 'bajo' : ''">{{ x.puntaje != null ? `${num(x.puntaje)} de ${num(x.maximo)}` : x.estado === 'NO_PRESENTADA' ? 'no presentada' : 'sin nota' }}</td><td class="py-1 text-right">{{ num(x.curso) }}</td></tr></tbody></table>
          </div>
         </li>
         <li v-for="t in tipos" :key="t">· {{ TIPOS[t] }}: <strong>{{ num(e.por_tipo[t]) }}</strong> (su curso: {{ num(data.curso_promedio.por_tipo[t]) }})</li>
         <li v-if="data.total_actividades">· Últimas {{ data.semanas }} semanas: <strong>{{ num(e.ultimas) }}</strong>; antes: {{ num(e.anteriores) }}</li>
         <li v-if="data.total_actividades">· No se presentó a <strong>{{ e.no_presentadas }}</strong>; sin nota registrada: {{ e.sin_nota }}</li>
         <li v-if="data.total_tareas">· Tareas: {{ e.tareas.entregadas }} entregada(s), <strong>{{ e.tareas.no_entregadas }} sin entregar</strong> ({{ e.tareas.seguidas_sin_entregar }} seguida(s) al final), {{ e.tareas.por_revisar }} por revisar</li>
        </ul>
       </td></tr>
      </template>
     </tbody>
    </table>
   </div>
   <p v-if="data.trimestres.length" class="mt-2 text-xs text-slate-500">Las columnas "Trimestre" son notas de cierre cargadas por trimestre; no entran en los promedios por actividad. En rojo, menos de 51.</p>
   <div class="mt-8 flex flex-wrap gap-3 text-sm">
    <RouterLink to="/calificaciones" class="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700">Registrar evaluaciones</RouterLink>
    <RouterLink to="/tareas" class="px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 hover:border-blue-500">Registrar tareas</RouterLink>
   </div>
  </template>
 </section>
</template>

<style scoped>
.campo { display: block; margin-top: .25rem; border: 1px solid #cbd5e1; border-radius: .5rem; padding: .5rem .75rem; background: #fff; color: #0f172a; }
.celda { padding: .6rem .75rem; text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.bajo { color: #dc2626; font-weight: 600; }
:global(.dark .bajo) { color: #f87171; }
</style>
