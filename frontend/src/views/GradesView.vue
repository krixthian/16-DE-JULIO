<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import api from '../services/api'
import { useUserStore } from '../stores/user'
const user=useUserStore()
const manager=computed(()=>['Admin','Director'].includes(user.user?.rol))
const ctx=ref({asignaciones:[],gestiones:[],periodos:[]}),assignmentId=ref(''),loadedAssignment=ref(null),evaluations=ref([]),sheet=ref(null)
const busy=ref(false),saving=ref(false),error=ref(''),notice=ref(''),dirty=ref(false),correction=ref(''),editForm=ref(null),formDirty=ref(false)
const period=ref({id:null,gestion_id:'',numero:1,fecha_inicio:'',fecha_fin:''}),periodDirty=ref(false)
const anyDirty=computed(()=>dirty.value||formDirty.value||periodDirty.value)
const statuses=[['CALIFICADA','Calificada'],['PENDIENTE','Pendiente'],['NO_PRESENTADA','No presentada'],['EXENTA','Exenta']]
const assignment=computed(()=>ctx.value.asignaciones.find(a=>a.id===Number(loadedAssignment.value)))
const periodsForForm=computed(()=>ctx.value.periodos.filter(p=>p.gestion_id===assignment.value?.gestion_id))
const periodRows=computed(()=>ctx.value.periodos.filter(p=>p.gestion_id===Number(period.value.gestion_id)))
const ready=computed(()=>!busy.value&&!saving.value)
const noteCounts=computed(()=>({calificadas:sheet.value?.estudiantes.filter(s=>s.estado==='CALIFICADA').length||0,pendientes:sheet.value?.estudiantes.filter(s=>!s.estado).length||0}))
function msg(e){const d=e.response?.data?.detail;return Array.isArray(d)?d.map(x=>`${x.loc.slice(1).join('.')}: ${x.msg.replace('Value error, ','')}`).join(' · '):d||'No se pudo conectar con el servidor. Intenta de nuevo.'}
function discard(){return !anyDirty.value||window.confirm('Hay cambios sin guardar. ¿Quieres descartarlos?')}
async function context(){ctx.value=(await api.get('/calificaciones/contexto')).data;if(!assignmentId.value)assignmentId.value=ctx.value.asignaciones[0]?.id||'';if(!period.value.gestion_id)period.value.gestion_id=ctx.value.gestiones[0]?.id||''}
async function initialize(){busy.value=true;error.value='';try{await context()}catch(e){error.value=msg(e)}finally{busy.value=false}}
async function loadEvaluations(){
 if(!assignmentId.value||!discard())return
 busy.value=true;error.value='';notice.value='';sheet.value=null;editForm.value=null;dirty.value=false;formDirty.value=false
 try{evaluations.value=(await api.get('/calificaciones/evaluaciones',{params:{asignacion_id:assignmentId.value}})).data;loadedAssignment.value=Number(assignmentId.value)}
 catch(e){error.value=msg(e);loadedAssignment.value=null;evaluations.value=[]}finally{busy.value=false}
}
function startEvaluation(e=null){
 if(!discard())return
 dirty.value=false;sheet.value=null;error.value='';notice.value='';formDirty.value=false
 editForm.value=e?{...e,motivo_correccion:''}:{asignacion_id:loadedAssignment.value,periodo_id:periodsForForm.value[0]?.id||'',titulo:'',tipo:'PRUEBA',fecha_aplicacion:'',puntaje_maximo:'',dimension:'',motivo_correccion:''}
}
function cancelEvaluation(){if(!formDirty.value||window.confirm('¿Descartar los cambios de la evaluación?')){editForm.value=null;formDirty.value=false}}
async function saveEvaluation(){
 saving.value=true;error.value='';notice.value=''
 try{
  const f=editForm.value;const body={asignacion_id:Number(f.asignacion_id),periodo_id:Number(f.periodo_id),titulo:f.titulo.trim(),tipo:f.tipo,fecha_aplicacion:f.fecha_aplicacion,puntaje_maximo:String(f.puntaje_maximo),dimension:f.dimension?.trim()||null}
  if(f.id)await api.put(`/calificaciones/evaluaciones/${f.id}`,{...body,revision:f.revision,motivo_correccion:f.motivo_correccion.trim()})
  else await api.post('/calificaciones/evaluaciones',body)
  editForm.value=null;formDirty.value=false
  evaluations.value=(await api.get('/calificaciones/evaluaciones',{params:{asignacion_id:loadedAssignment.value}})).data
  notice.value='Evaluación guardada. Abre «Registrar notas» para completar la lista.'
 }catch(e){error.value=msg(e)}finally{saving.value=false}
}
async function loadNotes(id){
 if(!discard())return
 busy.value=true;error.value='';notice.value='';editForm.value=null;formDirty.value=false;dirty.value=false;sheet.value=null
 try{sheet.value=(await api.get(`/calificaciones/evaluaciones/${id}/notas`)).data;correction.value=''}catch(e){error.value=msg(e)}finally{busy.value=false}
}
function changed(s){if(s.estado!=='CALIFICADA')s.puntaje=null;dirty.value=true;notice.value=''}
async function saveNotes(){
 saving.value=true;error.value='';notice.value=''
 try{
  const body={revision:sheet.value.revision,motivo_correccion:correction.value.trim()||null,estudiantes:sheet.value.estudiantes.map(s=>({matricula_id:s.matricula_id,estado:s.estado,puntaje:s.estado==='CALIFICADA'&&s.puntaje!==''&&s.puntaje!==null?String(s.puntaje):null}))}
  sheet.value=(await api.put(`/calificaciones/evaluaciones/${sheet.value.evaluacion.id}/notas`,body)).data
  dirty.value=false;correction.value='';notice.value='Calificaciones guardadas correctamente.'
 }catch(e){error.value=msg(e)}finally{saving.value=false}
}
function resetPeriod(){period.value={id:null,gestion_id:period.value.gestion_id,numero:1,fecha_inicio:'',fecha_fin:''};periodDirty.value=false}
function editPeriod(p){if(!periodDirty.value||window.confirm('¿Descartar los cambios del trimestre?')){period.value={...p};periodDirty.value=false}}
async function savePeriod(){
 saving.value=true;error.value='';notice.value=''
 try{
  const p=period.value;const body={gestion_id:Number(p.gestion_id),numero:Number(p.numero),fecha_inicio:p.fecha_inicio,fecha_fin:p.fecha_fin}
  if(p.id)await api.put(`/calificaciones/periodos/${p.id}`,body);else await api.post('/calificaciones/periodos',body)
  resetPeriod();await context();notice.value='Trimestre guardado correctamente.'
 }catch(e){error.value=msg(e)}finally{saving.value=false}
}
function unload(e){if(anyDirty.value){e.preventDefault();e.returnValue=''}}
onMounted(()=>{initialize();window.addEventListener('beforeunload',unload)})
onBeforeUnmount(()=>window.removeEventListener('beforeunload',unload))
onBeforeRouteLeave(()=>discard())
</script>

<template>
 <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs uppercase tracking-widest font-semibold text-blue-600 dark:text-blue-400 mb-2">Registro escolar</p>
  <h1 class="text-3xl font-bold">Calificaciones</h1>
  <p class="mt-2 text-slate-500 dark:text-slate-400">Registra evaluaciones parciales y notas durante el trimestre. Una nota cero se conserva como un resultado válido.</p>
  <div v-if="error" role="alert" class="mt-5 p-4 rounded-xl bg-red-50 text-red-800 border border-red-200">{{ error }}</div>
  <div v-if="notice" role="status" class="mt-5 p-4 rounded-xl bg-green-50 text-green-800 border border-green-200">{{ notice }}</div>
  <details v-if="manager" class="panel mt-6">
   <summary class="font-semibold cursor-pointer">Configurar trimestres</summary>
   <p class="text-sm text-slate-500 mt-2">Registra las fechas aprobadas por el colegio. Los trimestres deben estar ordenados y no solaparse.</p>
   <form class="grid md:grid-cols-2 xl:grid-cols-4 gap-4 mt-4" @submit.prevent="savePeriod" @input="periodDirty=true" @change="periodDirty=true">
    <label class="label">Gestión<select v-model.number="period.gestion_id" class="field" required :disabled="!!period.id||!ready"><option value="" disabled>Selecciona una gestión</option><option v-for="g in ctx.gestiones" :key="g.id" :value="g.id">{{ g.anio }}</option></select></label>
    <label class="label">Trimestre<select v-model.number="period.numero" class="field" required :disabled="!!period.id||!ready"><option v-for="n in 3" :key="n" :value="n">{{ n }}° trimestre</option></select></label>
    <label class="label">Inicio del trimestre<input v-model="period.fecha_inicio" type="date" class="field" required :disabled="!ready" /></label>
    <label class="label">Fin del trimestre<input v-model="period.fecha_fin" type="date" :min="period.fecha_inicio" class="field" required :disabled="!ready" /></label>
    <div class="flex flex-wrap gap-2 md:col-span-2 xl:col-span-4"><button class="primary" :disabled="!ready||!period.gestion_id">{{ period.id?'Guardar cambios del trimestre':'Registrar trimestre' }}</button><button v-if="period.id" type="button" class="secondary" :disabled="!ready" @click="resetPeriod">Cancelar edición</button></div>
   </form>
   <ul class="mt-4 divide-y divide-slate-200 dark:divide-slate-700"><li v-for="p in periodRows" :key="p.id" class="py-3 flex flex-wrap justify-between gap-2 text-sm"><span>{{ p.numero }}° trimestre · {{ p.fecha_inicio||'Inicio pendiente' }} — {{ p.fecha_fin||'Fin pendiente' }}</span><button class="link" :disabled="!ready" @click="editPeriod(p)">Editar trimestre {{ p.numero }}</button></li></ul>
   <p v-if="!periodRows.length" class="mt-3 text-sm text-slate-500">No hay trimestres en esta gestión.</p>
  </details>
  <form class="panel mt-6 flex flex-wrap items-end gap-4" @submit.prevent="loadEvaluations">
   <label class="label flex-1 min-w-48">Curso, materia y docente<select v-model.number="assignmentId" required class="field" :disabled="!ready"><option value="" disabled>Selecciona una asignación</option><option v-for="a in ctx.asignaciones" :key="a.id" :value="a.id">{{ a.gestion_anio }} · {{ a.curso_nombre }} · {{ a.materia_nombre }} · {{ a.docente_nombre }} (desde {{ a.vigente_desde }})</option></select></label>
   <button class="primary" :disabled="!ready||!assignmentId">{{ busy?'Cargando…':'Consultar evaluaciones' }}</button>
  </form>
  <p v-if="!busy&&!ctx.asignaciones.length" class="mt-4 text-slate-500">No hay asignaciones docentes disponibles. Dirección debe asignar una materia y curso al docente antes de crear evaluaciones.</p>
  <template v-if="assignment">
   <div class="flex flex-wrap items-center justify-between gap-4 mt-6 mb-4"><div><h2 class="text-xl font-semibold">{{ assignment.curso_nombre }} · {{ assignment.materia_nombre }}</h2><p class="text-sm text-slate-500 mt-1">Gestión {{ assignment.gestion_anio }} · {{ assignment.docente_nombre }}</p></div><button class="primary" :disabled="!ready||!periodsForForm.length" @click="startEvaluation()">+ Crear evaluación</button></div>
   <p v-if="!periodsForForm.length" class="mb-4 bg-amber-50 text-amber-900 rounded-xl p-4">Dirección debe configurar los trimestres de esta gestión para crear evaluaciones.</p>
   <form v-if="editForm" class="panel mb-5" @submit.prevent="saveEvaluation" @input="formDirty=true" @change="formDirty=true">
    <h3 class="text-lg font-semibold mb-4">{{ editForm.id?'Editar evaluación':'Nueva evaluación parcial' }}</h3>
    <div class="grid md:grid-cols-2 gap-4">
     <label class="label md:col-span-2">Título<input v-model="editForm.titulo" maxlength="160" required class="field" :disabled="!ready" placeholder="Ej.: Prueba de operaciones básicas" /></label>
     <label class="label">Trimestre<select v-model.number="editForm.periodo_id" required class="field" :disabled="!ready"><option value="" disabled>Selecciona un trimestre</option><option v-for="p in periodsForForm" :key="p.id" :value="p.id">{{ p.numero }}° trimestre</option></select></label>
     <label class="label">Tipo<select v-model="editForm.tipo" required class="field" :disabled="!ready"><option value="PRUEBA">Prueba</option><option value="TRABAJO">Trabajo</option><option value="PROYECTO">Proyecto</option><option value="ORAL">Oral</option><option value="OTRA">Otra</option></select></label>
     <label class="label">Fecha de aplicación<input v-model="editForm.fecha_aplicacion" type="date" required class="field" :disabled="!ready" /></label>
     <label class="label">Puntaje máximo<input v-model="editForm.puntaje_maximo" type="number" min="0.01" max="999999.99" step="0.01" required class="field" :disabled="!ready" placeholder="Ej.: 100" /></label>
     <label class="label md:col-span-2">Dimensión (opcional)<input v-model="editForm.dimension" maxlength="60" class="field" :disabled="!ready" placeholder="Según la planilla del colegio" /></label>
     <label v-if="editForm.id" class="label md:col-span-2">Motivo de corrección<input v-model="editForm.motivo_correccion" required maxlength="500" class="field" :disabled="!ready" /></label>
    </div>
    <p class="text-sm text-slate-500 mt-4">Cuando tenga notas, se conservarán la fecha, el trimestre, la dimensión y el puntaje máximo para proteger el historial.</p>
    <div class="flex justify-end gap-3 mt-5"><button type="button" class="secondary" :disabled="!ready" @click="cancelEvaluation">Cancelar</button><button class="primary" :disabled="!ready">Guardar evaluación</button></div>
   </form>
   <div class="panel !p-0 overflow-x-auto"><table class="w-full text-sm text-left"><thead class="bg-slate-50 dark:bg-slate-900/40"><tr><th class="cell">Evaluación</th><th class="cell">Fecha</th><th class="cell">Trimestre</th><th class="cell">Máximo</th><th class="cell">Acciones</th></tr></thead><tbody class="divide-y divide-slate-100 dark:divide-slate-700"><tr v-for="e in evaluations" :key="e.id"><td class="cell font-medium">{{ e.titulo }}</td><td class="cell whitespace-nowrap">{{ e.fecha_aplicacion }}</td><td class="cell">{{ ctx.periodos.find(p=>p.id===e.periodo_id)?.numero }}°</td><td class="cell">{{ e.puntaje_maximo }}</td><td class="cell"><div class="flex flex-wrap gap-3"><button class="link" :disabled="!ready" @click="loadNotes(e.id)">Registrar notas</button><button class="link" :disabled="!ready" @click="startEvaluation(e)">Editar evaluación</button></div></td></tr><tr v-if="!evaluations.length"><td class="p-8 text-center text-slate-500" colspan="5">Todavía no hay evaluaciones para esta asignación.</td></tr></tbody></table></div>
  </template>
  <form v-if="sheet" class="mt-7" @submit.prevent="saveNotes">
   <div class="flex flex-wrap justify-between items-center gap-3 mb-4"><div><h2 class="text-xl font-semibold">Notas · {{ sheet.evaluacion.titulo }}</h2><p class="text-sm text-slate-500 mt-1">{{ sheet.evaluacion.fecha_aplicacion }} · Puntaje máximo: {{ sheet.evaluacion.puntaje_maximo }}</p></div><span class="text-sm text-slate-500">{{ dirty?'Cambios sin guardar':`${noteCounts.calificadas} calificadas · ${noteCounts.pendientes} sin registrar` }}</span></div>
   <p v-if="sheet.registros_fuera_lista" class="p-4 mb-4 bg-red-50 text-red-800 rounded-xl">Hay notas fuera de las matrículas vigentes. Dirección debe revisar el historial antes de guardar.</p>
   <div class="panel !p-0 overflow-x-auto"><table class="w-full text-left text-sm"><thead class="bg-slate-50 dark:bg-slate-900/40"><tr><th class="cell">Estudiante</th><th class="cell">Estado</th><th class="cell">Puntaje</th></tr></thead><tbody class="divide-y divide-slate-100 dark:divide-slate-700"><tr v-for="s in sheet.estudiantes" :key="s.matricula_id"><td class="cell"><span class="font-medium">{{ s.apellido }}, {{ s.nombre }}</span><span v-if="s.origen==='SIMULADO'" class="block text-xs text-slate-500 mt-1">Datos simulados</span></td><td class="cell"><select v-model="s.estado" :aria-label="`Estado de ${s.nombre} ${s.apellido}`" class="field min-w-40" :disabled="!ready" @change="changed(s)"><option :value="null" :disabled="!!s.registrado_en">Sin registrar</option><option v-for="[v,label] in statuses" :key="v" :value="v">{{ label }}</option></select></td><td class="cell"><input v-model="s.puntaje" :aria-label="`Puntaje de ${s.nombre} ${s.apellido}`" type="number" min="0" :max="sheet.evaluacion.puntaje_maximo" step="0.01" :required="s.estado==='CALIFICADA'" :disabled="!ready||s.estado!=='CALIFICADA'" class="field min-w-28" placeholder="Sin nota" @input="dirty=true;notice=''" /></td></tr><tr v-if="!sheet.estudiantes.length"><td colspan="3" class="p-8 text-center text-slate-500">No hay matrículas vigentes en la fecha de aplicación.</td></tr></tbody></table></div>
   <p class="mt-3 text-sm text-slate-500">Pendiente, no presentada y exenta se guardan sin puntaje. No se calcula una nota trimestral oficial con estas evaluaciones.</p>
   <label v-if="sheet.estudiantes.some(s=>s.registrado_en)" class="label mt-4">Motivo de corrección de notas<input v-model="correction" maxlength="500" class="field" placeholder="Obligatorio al cambiar notas guardadas" :disabled="!ready" @input="dirty=true" /></label>
   <div class="flex flex-wrap justify-end gap-3 mt-5"><button type="button" class="secondary" :disabled="!ready" @click="loadNotes(sheet.evaluacion.id)">Recargar notas</button><button class="primary" :disabled="!ready||!sheet.estudiantes.length||!dirty||!!sheet.registros_fuera_lista">{{ saving?'Guardando…':'Guardar calificaciones' }}</button></div>
  </form>
 </section>
</template>
<style scoped>
.panel{@apply p-5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800;}
.label{@apply block text-sm font-medium;}
.field{@apply block w-full mt-1 px-3 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50;}
.primary{@apply px-4 py-2.5 rounded-lg bg-blue-600 text-white font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed;}
.secondary{@apply px-4 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 text-sm hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50;}
.link{@apply text-blue-600 dark:text-blue-400 font-semibold hover:underline disabled:opacity-50;}
.cell{@apply px-4 py-3;}
</style>
