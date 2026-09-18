<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import api from '../services/api'
import { useUserStore } from '../stores/user'
const store=useUserStore()
const manager=computed(()=>['Admin','Director'].includes(store.user?.rol))
const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
const courses=ref([]),course=ref(''),day=ref(today()),sheet=ref(null),error=ref(''),notice=ref(''),busy=ref(false),saving=ref(false),dirty=ref(false),reason=ref('')
const statuses=[['PRESENTE','Presente'],['FALTA','Falta'],['ATRASO','Atraso'],['LICENCIA','Licencia']]
const counts=computed(()=>Object.fromEntries([...statuses,[null,'Sin registro']].map(([key,label])=>[label,sheet.value?.estudiantes.filter(s=>s.estado===key).length||0])))
const changed=()=>{dirty.value=true;notice.value=''}
const message=e=>{const d=e.response?.data?.detail;return Array.isArray(d)?d.map(x=>x.msg.replace('Value error, ','')).join(' · '):d||'No se pudo conectar con el servidor. Intenta nuevamente.'}
async function loadCourses(){
  busy.value=true;error.value=''
  try{courses.value=(await api.get('/asistencia/cursos')).data;if(!course.value)course.value=courses.value[0]?.id||''}
  catch(e){error.value=message(e)}finally{busy.value=false}
}
async function load(){
  if(!course.value||!day.value)return
  if(dirty.value&&!window.confirm('Hay cambios sin guardar. ¿Quieres descartarlos y cargar otra lista?'))return
  busy.value=true;error.value='';notice.value='';sheet.value=null;dirty.value=false
  try{sheet.value=(await api.get(`/asistencia/${course.value}/${day.value}`)).data;reason.value=''}
  catch(e){error.value=message(e)}finally{busy.value=false}
}
function markPending(){sheet.value.estudiantes.forEach(s=>{if(!s.estado)s.estado='PRESENTE'});changed()}
function stateChanged(s){if(!s.estado||s.estado==='PRESENTE')s.justificada=null;if(!s.estado)s.observacion=null;changed()}
async function save(){
  saving.value=true;error.value='';notice.value=''
  try{
    const s=sheet.value
    const payload={revision:s.revision,es_lectiva:s.es_lectiva,motivo_no_lectiva:s.es_lectiva?null:s.motivo_no_lectiva||null,motivo_correccion:reason.value.trim()||null,
      estudiantes:s.estudiantes.map(x=>({matricula_id:x.matricula_id,estado:s.es_lectiva?x.estado:null,justificada:s.es_lectiva?x.justificada:null,observacion:s.es_lectiva?x.observacion?.trim()||null:null}))}
    sheet.value=(await api.put(`/asistencia/${s.curso_id}/${s.fecha}`,payload)).data
    dirty.value=false;reason.value='';notice.value='Asistencia guardada. Puedes volver a consultar esta fecha para revisar o corregir la lista.'
  }catch(e){error.value=message(e)}finally{saving.value=false}
}
function unload(e){if(dirty.value){e.preventDefault();e.returnValue=''}}
onMounted(()=>{loadCourses();window.addEventListener('beforeunload',unload)})
onBeforeUnmount(()=>window.removeEventListener('beforeunload',unload))
onBeforeRouteLeave(()=>!dirty.value||window.confirm('Hay cambios sin guardar. ¿Quieres salir y descartarlos?'))
</script>
<template>
 <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Registro escolar</p>
  <h1 class="text-3xl font-bold">Asistencia diaria</h1>
  <p class="mt-2 text-slate-500 dark:text-slate-400">Consulta una fecha y registra la asistencia del curso. Los estudiantes pendientes permanecen sin registro.</p>
  <form @submit.prevent="load" class="flex flex-wrap items-end gap-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 my-6">
   <label class="flex-1 min-w-48 text-sm font-medium">Curso<select v-model="course" required class="field" :disabled="busy||saving"><option value="" disabled>Selecciona un curso</option><option v-for="c in courses" :key="c.id" :value="c.id">{{ c.nombre }}</option></select></label>
   <label class="text-sm font-medium">Fecha<input v-model="day" type="date" required :max="today()" class="field" :disabled="busy||saving" /></label>
   <button class="primary" :disabled="busy||saving||!course">{{ busy?'Cargando…':'Consultar lista' }}</button>
  </form>
  <p v-if="!busy&&!courses.length&&!error" class="p-5 border rounded-xl text-slate-500">{{ manager?'Todavía no hay cursos registrados. Crea un curso en Administración escolar.':'No tienes cursos asignados. Dirección debe registrar tus asignaciones docentes.' }}</p>
  <p v-if="error" role="alert" class="bg-red-50 text-red-800 border border-red-200 rounded-xl p-4 mb-5">{{ error }} <button v-if="!courses.length" class="underline" @click="loadCourses">Reintentar</button></p>
  <p v-if="notice" role="status" class="bg-green-50 text-green-800 border border-green-200 rounded-xl p-4 mb-5">{{ notice }}</p>
  <template v-if="sheet">
   <div class="flex flex-wrap justify-between items-center gap-3 mb-4"><h2 class="text-xl font-semibold">{{ sheet.curso }} · {{ sheet.fecha }}</h2><span class="text-sm text-slate-500">{{ dirty?'Cambios sin guardar':sheet.jornada_registrada?'Jornada registrada':'Jornada sin registro' }}</span></div>
   <div class="flex flex-wrap gap-3 mb-5"><div v-for="(count,label) in counts" :key="label" class="px-4 py-3 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700"><span class="text-sm text-slate-500 dark:text-slate-400">{{ label }}</span><strong class="ml-3">{{ sheet.es_lectiva?count:'—' }}</strong></div></div>
   <div v-if="manager" class="mb-5 p-4 rounded-xl border border-slate-200 dark:border-slate-700">
    <label class="flex gap-2 items-center font-medium"><input v-model="sheet.es_lectiva" type="checkbox" :disabled="saving" @change="changed" /> Hubo clases en esta fecha</label>
    <label v-if="!sheet.es_lectiva" class="block text-sm mt-3">Motivo del día sin clases<input v-model="sheet.motivo_no_lectiva" maxlength="200" placeholder="Ej.: suspensión de actividades" class="field" :disabled="saving" @input="changed" /></label>
   </div>
   <p v-if="!sheet.es_lectiva" class="p-5 mb-5 rounded-xl bg-amber-50 text-amber-900">Día sin clases{{ sheet.motivo_no_lectiva?`: ${sheet.motivo_no_lectiva}`:'' }}. No se contabiliza como falta.</p>
   <div v-else class="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
    <div class="p-4 flex flex-wrap justify-between items-center gap-3 border-b border-slate-200 dark:border-slate-700"><span>{{ sheet.estudiantes.length }} estudiantes con matrícula vigente</span><button class="secondary" :disabled="saving||!sheet.estudiantes.some(s=>!s.estado)" @click="markPending">Marcar pendientes como presentes</button></div>
    <div class="overflow-x-auto"><table class="w-full text-left text-sm"><thead class="bg-slate-50 dark:bg-slate-900/40 text-slate-500 dark:text-slate-300"><tr><th class="cell">Estudiante</th><th class="cell">Estado</th><th class="cell">Justificación</th><th class="cell">Observación</th></tr></thead>
     <tbody class="divide-y divide-slate-100 dark:divide-slate-700"><tr v-for="s in sheet.estudiantes" :key="s.matricula_id">
      <td class="cell min-w-48"><span class="font-medium">{{ s.apellido }}, {{ s.nombre }}</span><span v-if="s.origen==='SIMULADO'" class="block text-xs text-slate-500 mt-1">Datos simulados</span></td>
      <td class="cell"><select v-model="s.estado" :aria-label="`Estado de ${s.nombre} ${s.apellido}`" class="field min-w-36" :disabled="saving" @change="stateChanged(s)"><option :value="null" :disabled="!!s.registrado_en">Sin registro</option><option v-for="[value,label] in statuses" :key="value" :value="value">{{ label }}</option></select></td>
      <td class="cell"><select v-model="s.justificada" :aria-label="`Justificación de ${s.nombre} ${s.apellido}`" class="field min-w-36" :disabled="saving||!s.estado||s.estado==='PRESENTE'" @change="changed"><option :value="null">{{ !s.estado||s.estado==='PRESENTE'?'No corresponde':'Sin confirmar' }}</option><option :value="true">Justificada</option><option :value="false">Injustificada</option></select></td>
      <td class="cell"><input v-model="s.observacion" :aria-label="`Observación de ${s.nombre} ${s.apellido}`" maxlength="500" class="field min-w-48" placeholder="Opcional" :disabled="saving||!s.estado" @input="changed" /></td>
     </tr><tr v-if="!sheet.estudiantes.length"><td colspan="4" class="p-10 text-center text-slate-500">No hay estudiantes con matrícula vigente en esta fecha.</td></tr></tbody></table></div>
   </div>
   <div v-if="sheet.jornada_registrada" class="mt-5"><label class="text-sm font-medium">Motivo de corrección<input v-model="reason" maxlength="500" placeholder="Obligatorio si modificas información ya guardada" class="field" :disabled="saving" @input="changed" /></label></div>
   <div class="flex justify-end mt-5"><button class="primary" :disabled="saving||busy||(!sheet.es_lectiva&&!manager)||(!dirty&&sheet.jornada_registrada)" @click="save">{{ saving?'Guardando…':'Guardar asistencia' }}</button></div>
  </template>
 </section>
</template>
<style scoped>
.field{@apply block w-full mt-1 px-3 py-2.5 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50;}
.primary{@apply px-4 py-2.5 rounded-lg bg-blue-600 text-white font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed;}
.secondary{@apply px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-sm hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50;}
.cell{@apply px-4 py-3;}
</style>
