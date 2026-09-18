<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import api from '../services/api'
const assignments=ref([]),assignment=ref(''),tasks=ref([]),loaded=ref(null),sheet=ref(null),form=ref(null)
const busy=ref(false),error=ref(''),notice=ref(''),dirty=ref(false),reason=ref(''),filter=ref('')
const statuses=[['PENDIENTE','Pendiente'],['ENTREGADA','Entregada'],['NO_ENTREGADA','No entregada'],['EXENTA','Exenta']]
const message=e=>{const d=e.response?.data?.detail;return Array.isArray(d)?d.map(x=>x.msg.replace('Value error, ','')).join(' · '):d||'No se pudo conectar con el servidor.'}
const format=v=>v?v.replace('T',' ').slice(0,16):'—'
const localNow=()=>{const d=new Date();return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)}
const clock=ref(Date.now())
let clockTimer
const expired=s=>s.estado==='PENDIENTE'&&sheet.value&&clock.value>new Date(sheet.value.tarea.fecha_limite).getTime()
const counts=computed(()=>({...Object.fromEntries([...statuses,[null,'Sin registro']].map(([k,l])=>[l,sheet.value?.estudiantes.filter(s=>s.estado===k&&!expired(s)).length||0])), 'Vencida, por revisar':sheet.value?.estudiantes.filter(expired).length||0}))
const visible=computed(()=>tasks.value.filter(t=>t.titulo.toLowerCase().includes(filter.value.toLowerCase())))
function discard(){return !dirty.value||window.confirm('Hay cambios sin guardar. ¿Quieres descartarlos?')}
function changed(){dirty.value=true;notice.value=''}
async function init(){busy.value=true;try{assignments.value=(await api.get('/tareas/contexto')).data.asignaciones;assignment.value=assignments.value[0]?.id||''}catch(e){error.value=message(e)}finally{busy.value=false}}
async function load(){
 if(!assignment.value||!discard())return
 busy.value=true;error.value='';notice.value='';sheet.value=null;form.value=null;dirty.value=false;tasks.value=[];loaded.value=null
 try{tasks.value=(await api.get('/tareas',{params:{asignacion_id:assignment.value}})).data;loaded.value=assignment.value}catch(e){error.value=message(e)}finally{busy.value=false}
}
function edit(t=null){
 if(!discard())return
 sheet.value=null;error.value='';notice.value='';dirty.value=false
 form.value=t?{...t,motivo_correccion:''}:{asignacion_id:Number(loaded.value),titulo:'',fecha_asignacion:localNow(),fecha_limite:'',evaluacion_id:null}
}
async function saveTask(){
 busy.value=true;error.value='';notice.value=''
 try{
  const f=form.value,payload={asignacion_id:f.asignacion_id,titulo:f.titulo,fecha_asignacion:f.fecha_asignacion,fecha_limite:f.fecha_limite,evaluacion_id:f.evaluacion_id}
  if(f.id){payload.revision=f.revision;payload.motivo_correccion=f.motivo_correccion}
  const {data}=await api[f.id?'put':'post'](f.id?`/tareas/${f.id}`:'/tareas',payload)
  tasks.value=[data,...tasks.value.filter(x=>x.id!==data.id)];form.value=null;dirty.value=false;notice.value='Tarea guardada.'
 }catch(e){error.value=message(e)}finally{busy.value=false}
}
async function open(t){
 if(!discard())return
 busy.value=true;error.value='';notice.value='';form.value=null;sheet.value=null;dirty.value=false
 try{sheet.value=(await api.get(`/tareas/${t.id}/entregas`)).data;reason.value=''}catch(e){error.value=message(e)}finally{busy.value=false}
}
function stateChanged(s){if(s.estado==='ENTREGADA'){if(!s.fecha_entrega)s.fecha_entrega=localNow()}else s.fecha_entrega=null;changed()}
async function save(){
 busy.value=true;error.value='';notice.value=''
 try{
  const s=sheet.value
  sheet.value=(await api.put(`/tareas/${s.tarea.id}/entregas`,{revision:s.revision,motivo_correccion:reason.value.trim()||null,
   estudiantes:s.estudiantes.map(x=>({matricula_id:x.matricula_id,estado:x.estado,fecha_entrega:x.estado==='ENTREGADA'?x.fecha_entrega||null:null}))})).data
  dirty.value=false;reason.value='';notice.value='Seguimiento guardado. Las entregas fuera de plazo se calculan con su fecha real.'
 }catch(e){error.value=message(e)}finally{busy.value=false}
}
function unload(e){if(dirty.value){e.preventDefault();e.returnValue=''}}
onMounted(()=>{clockTimer=window.setInterval(()=>{clock.value=Date.now()},1000);init();window.addEventListener('beforeunload',unload)})
onBeforeUnmount(()=>{window.clearInterval(clockTimer);window.removeEventListener('beforeunload',unload)})
onBeforeRouteLeave(discard)
</script>
<template>
 <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Registro escolar</p>
  <h1 class="text-3xl font-bold">Seguimiento de tareas</h1>
  <p class="mt-2 text-slate-500 dark:text-slate-400">Organiza tareas por curso y materia y registra las entregas de cada estudiante.</p>
  <form @submit.prevent="load" class="panel flex flex-wrap items-end gap-4 my-6">
   <label class="flex-1 text-sm font-medium">Curso y materia<select v-model="assignment" class="field" required :disabled="busy"><option value="" disabled>Selecciona una asignación</option><option v-for="a in assignments" :key="a.id" :value="a.id">{{ a.gestion_anio }} · {{ a.curso_nombre }} · {{ a.materia_nombre }} · {{ a.docente_nombre }} ({{ a.vigente_desde }} a {{ a.vigente_hasta||'fin de gestión' }})</option></select></label>
   <button class="primary" :disabled="busy||!assignment">{{busy?'Cargando…':'Consultar tareas'}}</button>
  </form>
  <p v-if="!busy&&!assignments.length&&!error" class="panel">No hay asignaciones disponibles. Dirección debe registrar curso, materia y docente antes de crear tareas.</p>
  <p v-if="error" role="alert" class="panel bg-red-50 !text-red-800">{{error}} <button v-if="!assignments.length" @click="init" class="underline">Reintentar</button></p>
  <p v-if="notice" role="status" class="panel bg-green-50 !text-green-800">{{notice}}</p>
  <template v-if="loaded">
   <div class="flex flex-wrap gap-3 justify-between my-4"><label>Buscar tarea<input v-model="filter" class="field" placeholder="Título de la tarea" /></label><button class="primary self-end" @click="edit()" :disabled="busy">Crear tarea</button></div>
   <p class="text-sm text-slate-500 mb-4">La lista corresponde a la última asignación consultada. Las fechas y horas se registran en la hora local del colegio.</p>
   <div class="panel overflow-x-auto"><table class="w-full text-left text-sm"><thead><tr><th class="cell">Tarea</th><th class="cell">Asignación</th><th class="cell">Plazo</th><th class="cell">Acciones</th></tr></thead><tbody>
    <tr v-for="t in visible" :key="t.id" class="border-t border-slate-200 dark:border-slate-700"><td class="cell font-medium">{{t.titulo}}</td><td class="cell">{{format(t.fecha_asignacion)}}</td><td class="cell">{{format(t.fecha_limite)}}</td><td class="cell"><button class="secondary mr-2" @click="open(t)" :disabled="busy">Ver entregas</button><button class="secondary" @click="edit(t)" :disabled="busy">Editar</button></td></tr>
    <tr v-if="!visible.length"><td colspan="4" class="cell text-slate-500">{{tasks.length?'No hay coincidencias.':'Aún no hay tareas para esta asignación.'}}</td></tr>
   </tbody></table></div>
  </template>
  <form v-if="form" @submit.prevent="saveTask" @input="changed" @change="changed" class="panel mt-6">
   <h2 class="text-xl font-semibold mb-4">{{form.id?'Editar tarea':'Nueva tarea'}}</h2>
   <fieldset :disabled="busy" class="grid md:grid-cols-2 gap-4">
    <label class="md:col-span-2">Título<input v-model="form.titulo" required maxlength="160" class="field" /></label>
    <label>Fecha y hora de asignación<input v-model="form.fecha_asignacion" type="datetime-local" required class="field" /></label>
    <label>Fecha y hora límite<input v-model="form.fecha_limite" type="datetime-local" required :min="form.fecha_asignacion" class="field" /></label>
    <label v-if="form.id" class="md:col-span-2">Motivo de corrección<input v-model="form.motivo_correccion" required maxlength="500" class="field" /></label>
   </fieldset>
   <p class="text-sm text-slate-500 my-4">Cuando existan registros de seguimiento, se conservarán las fechas. Este módulo no modifica calificaciones.</p>
   <button class="primary" :disabled="busy">Guardar tarea</button><button type="button" class="secondary ml-3" :disabled="busy" @click="()=>{if(discard()){form=null;dirty=false}}">Cancelar</button>
  </form>
  <section v-if="sheet" class="mt-6">
   <h2 class="text-xl font-semibold">{{sheet.tarea.titulo}}</h2>
   <p class="text-sm text-slate-500 mt-2">Plazo: {{format(sheet.tarea.fecha_limite)}}. Las nuevas tareas comienzan pendientes. Al vencer el plazo quedan por revisar; el docente confirma si no fueron entregadas.</p>
   <div class="flex flex-wrap gap-3 my-4"><div v-for="(n,label) in counts" :key="label" class="panel !mb-0">{{label}} <strong class="ml-2">{{n}}</strong></div></div>
   <p v-if="sheet.registros_fuera_lista" role="alert" class="panel text-red-700">Hay registros fuera de la lista. Dirección debe revisar las matrículas antes de guardar.</p>
   <div class="panel overflow-x-auto"><table class="w-full text-left text-sm"><thead><tr><th class="cell">Estudiante</th><th class="cell">Estado</th><th class="cell">Fecha real de entrega</th><th class="cell">Plazo al guardar</th></tr></thead><tbody>
    <tr v-for="s in sheet.estudiantes" :key="s.matricula_id" class="border-t border-slate-200 dark:border-slate-700">
     <td class="cell min-w-48">{{s.apellido}}, {{s.nombre}}<span v-if="s.origen==='SIMULADO'" class="block text-xs text-slate-500">Datos simulados</span></td>
     <td class="cell"><select v-model="s.estado" class="field min-w-40" :aria-label="`Estado de ${s.nombre}`" :disabled="busy" @change="stateChanged(s)"><option :value="null" :disabled="!!s.registrado_en">Sin registro</option><option v-for="[v,l] in statuses" :key="v" :value="v">{{v==='PENDIENTE'&&expired(s)?'Vencida, por revisar':l}}</option></select></td>
     <td class="cell"><input v-model="s.fecha_entrega" type="datetime-local" class="field" :aria-label="`Entrega de ${s.nombre}`" :disabled="busy||s.estado!=='ENTREGADA'" :min="sheet.tarea.fecha_asignacion" :max="localNow()" @input="changed" /></td>
     <td class="cell">{{s.estado==='ENTREGADA'&&s.fecha_entrega?(s.fecha_entrega>sheet.tarea.fecha_limite?'Fuera de plazo':'En plazo'):'—'}}</td>
    </tr><tr v-if="!sheet.estudiantes.length"><td colspan="4" class="cell">No hay matrículas vigentes al asignar esta tarea.</td></tr>
   </tbody></table></div>
   <p class="text-sm text-slate-500 my-4">Al marcar Entregada se completa la fecha y hora actual. Puedes corregirlas si recibiste la tarea antes. Pasar de Pendiente a un estado confirmado no requiere motivo.</p><label class="block my-4">Motivo de corrección<input v-model="reason" maxlength="500" class="field" placeholder="Obligatorio al modificar registros guardados" :disabled="busy" @input="changed" /></label>
   <button class="primary" :disabled="busy||!dirty||!sheet.estudiantes.length||!!sheet.registros_fuera_lista" @click="save">{{busy?'Guardando…':'Guardar seguimiento'}}</button>
  </section>
 </section>
</template>
<style scoped>
.field{@apply block w-full mt-1 px-3 py-2.5 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50;}
.panel{@apply p-5 mb-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800;}
.primary{@apply px-4 py-2.5 rounded-lg bg-blue-600 text-white font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed;}
.secondary{@apply px-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-sm hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50;}
.cell{@apply px-3 py-3;}
</style>
