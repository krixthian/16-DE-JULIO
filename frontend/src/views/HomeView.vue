<script setup>
import { computed, onMounted, ref } from 'vue'
import { useUserStore } from '../stores/user'
import api from '../services/api'
const store=useUserStore()
const manager=computed(()=>['Admin','Director'].includes(store.user?.rol))
const sections=[{key:'gestiones',label:'Gestiones',description:'Calendario escolar'},{key:'cursos',label:'Cursos',description:'Grados y paralelos'},{key:'estudiantes',label:'Estudiantes',description:'Registro de estudiantes'},{key:'matriculas',label:'Matrículas',description:'Permanencia por curso'},{key:'materias',label:'Materias',description:'Catálogo de materias'},{key:'asignaciones',label:'Asignaciones',description:'Docentes por curso y materia'}]
const counts=ref({}),pending=ref([]),error=ref(''),loading=ref(true)
async function load(){
  loading.value=true;error.value=''
  if(!manager.value){loading.value=false;return}
  try{
    const results=await Promise.all(sections.map(s=>api.get(`/escolar/${s.key}`)))
    counts.value=Object.fromEntries(sections.map((s,i)=>[s.key,results[i].data.length]))
    pending.value=results[0].data.filter(g=>!g.fecha_inicio||!g.fecha_fin)
  }catch(e){error.value='No se pudieron cargar los registros escolares. Comprueba la conexión con el backend.'}
  finally{loading.value=false}
}
onMounted(load)
</script>
<template>
  <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
    <p class="text-blue-600 dark:text-blue-400 text-xs font-semibold tracking-widest uppercase mb-2">Unidad Educativa 16 de Julio</p>
    <h1 class="text-3xl font-bold">Panel de control</h1>
    <p class="mt-2 text-slate-500 dark:text-slate-400">Bienvenido, {{ store.user?.nombre }}.</p>
    <template v-if="manager">
      <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }} <button class="underline" @click="load">Reintentar</button></div>
      <div class="grid sm:grid-cols-2 xl:grid-cols-3 gap-4 mt-8">
        <RouterLink v-for="s in sections" :key="s.key" :to="`/escolar/${s.key}`" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-6 hover:border-blue-500 hover:shadow-md transition">
          <h2 class="font-semibold">{{ s.label }}</h2><p class="text-4xl font-bold mt-4 text-blue-600 dark:text-blue-400">{{ loading ? '…' : counts[s.key] ?? '—' }}</p><p class="text-sm text-slate-500 dark:text-slate-400 mt-3">{{ s.description }}</p><span class="inline-block mt-5 text-sm text-blue-600 dark:text-blue-400 font-semibold">Abrir módulo →</span>
        </RouterLink>
      </div>
      <div v-if="pending.length" class="mt-6 p-5 border border-amber-200 rounded-xl bg-amber-50 text-amber-900"><h2 class="font-semibold">Calendario pendiente</h2><p class="mt-1">Completa las fechas de {{ pending.map(g=>g.anio).join(', ') }} para poder registrar matrículas.</p><RouterLink to="/escolar/gestiones" class="inline-block mt-3 underline font-semibold">Completar gestión</RouterLink></div>
      <div class="mt-6 p-6 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl"><h2 class="font-semibold">Registro escolar</h2><p class="text-slate-500 dark:text-slate-400 mt-2">Comienza por la gestión y sus cursos. Registra a los estudiantes y después sus matrículas, indicando las fechas y el origen real o simulado de los datos.</p></div>
    </template>
    <RouterLink v-if="['Admin','Director','Docente'].includes(store.user?.rol)" to="/asistencia" class="block mt-6 p-6 rounded-xl bg-blue-600 text-white hover:bg-blue-700"><h2 class="font-semibold">Asistencia diaria</h2><p class="mt-2">Consulta la lista de tu curso y registra presentes, faltas, atrasos y licencias.</p><span class="inline-block mt-3 font-semibold">Registrar asistencia →</span></RouterLink>
    <RouterLink v-if="['Admin','Director','Docente'].includes(store.user?.rol)" to="/calificaciones" class="block mt-6 p-6 rounded-xl border border-blue-200 dark:border-blue-800 bg-white dark:bg-slate-800 hover:border-blue-500"><h2 class="font-semibold">Calificaciones</h2><p class="mt-2 text-slate-500 dark:text-slate-400">Crea evaluaciones parciales y registra notas por materia y trimestre.</p><span class="inline-block mt-3 font-semibold text-blue-600 dark:text-blue-400">Registrar calificaciones →</span></RouterLink>
    <RouterLink v-if="['Admin','Director','Docente'].includes(store.user?.rol)" to="/tareas" class="block mt-6 p-6 rounded-xl border border-blue-200 dark:border-blue-800 bg-white dark:bg-slate-800 hover:border-blue-500"><h2 class="font-semibold">Seguimiento de tareas</h2><p class="mt-2 text-slate-500 dark:text-slate-400">Organiza tareas por materia y registra entregas, pendientes y exenciones.</p><span class="inline-block mt-3 font-semibold text-blue-600 dark:text-blue-400">Consultar tareas →</span></RouterLink>
    <div class="mt-6 p-6 rounded-xl border border-slate-200 dark:border-slate-700"><h2 class="font-semibold">Alertas de riesgo</h2><p class="text-slate-500 dark:text-slate-400 mt-2">La evaluación predictiva todavía no está disponible. XGBoost se incorporará en la siguiente etapa.</p></div>
  </section>
</template>
