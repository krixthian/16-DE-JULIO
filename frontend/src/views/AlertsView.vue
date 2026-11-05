<script setup>
import { etiquetaCodigo } from '../utils/estudiante'
import { ref, computed, onMounted } from 'vue'
import api from '../services/api'
const alerts=ref([]),summary=ref(null),people=ref([]),selected=ref(null),items=ref([]),history=ref([]),recs=ref(null),busy=ref(false),error=ref(''),notice=ref('')
const execution=ref(null),today=new Date().toISOString().slice(0,10)
const filter=ref({estado:'',gestion:'',curso:'',nivel:''}),form=ref({recomendacion:'',fecha_planificada:''}),closing=ref('')
const states=[['NUEVA','Nueva'],['EN_REVISION','En revisión'],['EN_SEGUIMIENTO','En seguimiento'],['CERRADA','Cerrada']]
const stepStates=[['PROPUESTA','Propuesta'],['APROBADA','Aprobada'],['EN_CURSO','En curso'],['REALIZADA','Realizada'],['CANCELADA','Cancelada']]
const label=(list,k)=>Object.fromEntries(list)[k]||k
const message=e=>{const d=e.response?.data?.detail;return Array.isArray(d)?d.map(x=>x.msg.replace('Value error, ','')).join(' · '):d||'No se pudo conectar con el servidor.'}
const score=v=>v.toFixed(3).replace('.',',')
const years=computed(()=>[...new Set(alerts.value.map(a=>a.gestion))])
const courses=computed(()=>[...new Map(alerts.value.filter(a=>!filter.value.gestion||a.gestion===Number(filter.value.gestion))
 .sort((a,b)=>a.grado-b.grado||a.curso.localeCompare(b.curso)).map(a=>[a.curso_id,`${a.curso} · ${a.gestion}`])).entries()])
const visible=computed(()=>alerts.value.filter(a=>(!filter.value.estado||a.estado===filter.value.estado)&&(!filter.value.gestion||a.gestion===Number(filter.value.gestion))
 &&(!filter.value.curso||a.curso_id===Number(filter.value.curso))&&(!filter.value.nivel||a.nivel===filter.value.nivel)))
const levelClass=n=>n==='ALTO'?'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200':'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'
const fields={estado:'Estado',responsable_id:'Responsable',motivo_cierre:'Motivo de cierre',accion_realizada:'Acción',resultado:'Resultado'}
const who=id=>people.value.find(p=>p.id===id)?.nombre||`Usuario ${id}`
const show=(k,v)=>v==null?'—':k==='responsable_id'?who(v):k==='estado'?label([...states,...stepStates],v):v
const changes=h=>h.antes?Object.keys(fields).filter(k=>k in h.despues&&h.antes[k]!==h.despues[k]).map(k=>`${fields[k]}: ${show(k,h.antes[k])} → ${show(k,h.despues[k])}`):[h.motivo]
async function load(){
 busy.value=true;error.value=''
 try{const [a,s,p]=await Promise.all([api.get('/alertas'),api.get('/alertas/resumen'),api.get('/alertas/responsables')]);alerts.value=a.data;summary.value=s.data;people.value=p.data}catch(e){error.value=message(e)}finally{busy.value=false}
}
async function loadDetail(){
 const id=selected.value.id
 const [i,h,r]=await Promise.all([api.get(`/alertas/${id}/intervenciones`),api.get(`/alertas/${id}/historial`),api.get(`/alertas/${id}/recomendaciones`)])
 items.value=i.data;history.value=h.data;recs.value=r.data
}
async function adopt(r){
 busy.value=true;error.value='';notice.value=''
 try{
  await api.post(`/alertas/${selected.value.id}/recomendaciones/${r.codigo}`)
  replace({...selected.value,intervenciones:selected.value.intervenciones+1,estado:selected.value.estado==='NUEVA'?'EN_SEGUIMIENTO':selected.value.estado})
  await loadDetail();notice.value=`Recomendación ${r.codigo} registrada como intervención propuesta.`
 }catch(e){error.value=message(e)}finally{busy.value=false}
}
function startExecution(i){
 const rule=recs.value?.reglas.find(r=>r.regla_version===i.regla_version)
 execution.value={id:i.id,tipo_accion:rule?.tipo_accion||'OTRA',fecha_ejecucion:today,accion_realizada:'',resultado:''}
}
async function saveExecution(){
 busy.value=true;error.value=''
 try{await api.patch(`/intervenciones/${execution.value.id}`,{estado:'REALIZADA',...execution.value,id:undefined});execution.value=null;await loadDetail();notice.value='Ejecución registrada.'}
 catch(e){error.value=message(e)}finally{busy.value=false}
}
async function open(a){
 selected.value=a;items.value=[];history.value=[];recs.value=null;execution.value=null;closing.value='';form.value={recomendacion:'',fecha_planificada:''};notice.value=''
 try{await loadDetail()}catch(e){error.value=message(e)}
}
function replace(a){alerts.value=alerts.value.map(x=>x.id===a.id?a:x);selected.value=a}
async function patch(body,text){
 busy.value=true;error.value='';notice.value=''
 try{replace((await api.patch(`/alertas/${selected.value.id}`,body)).data);await loadDetail();notice.value=text}catch(e){error.value=message(e)}finally{busy.value=false}
}
const setState=estado=>patch({estado,motivo_cierre:estado==='CERRADA'?closing.value.trim():null},'Estado de la alerta actualizado.')
const assign=id=>patch({responsable_id:Number(id)},'Responsable asignado.')
async function propose(){
 busy.value=true;error.value=''
 try{
  await api.post(`/alertas/${selected.value.id}/intervenciones`,{recomendacion:form.value.recomendacion,fecha_planificada:form.value.fecha_planificada||null})
  form.value={recomendacion:'',fecha_planificada:''}
  replace({...selected.value,intervenciones:selected.value.intervenciones+1,estado:selected.value.estado==='NUEVA'?'EN_SEGUIMIENTO':selected.value.estado})
  await loadDetail();notice.value='Intervención registrada.'
 }catch(e){error.value=message(e)}finally{busy.value=false}
}
async function advance(i,estado){
 if(estado==='REALIZADA')return startExecution(i)
 busy.value=true;error.value=''
 try{await api.patch(`/intervenciones/${i.id}`,{estado});await loadDetail()}catch(e){error.value=message(e)}finally{busy.value=false}
}
onMounted(load)
</script>
<template>
 <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Alerta temprana</p>
  <h1 class="text-3xl font-bold">Alertas de riesgo de abandono</h1>
  <p class="mt-2 text-slate-500 dark:text-slate-400 max-w-3xl">Predicción XGBoost al cierre del 1.er trimestre. El modelo apoya, no sustituye, el criterio docente.</p>
  <div class="mt-4 rounded-xl border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40 text-blue-900 dark:text-blue-100 p-4 text-sm max-w-4xl">
   <strong>Nivel = ranking de prioridad.</strong> {{ summary?.nota || 'El puntaje no está calibrado: ordena la revisión, no es un riesgo absoluto.' }}
  </div>
  <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }}</div>
  <div v-if="notice" class="mt-6 bg-green-50 text-green-800 rounded-xl p-4">{{ notice }}</div>
  <div v-if="summary" class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
   <div class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5"><p class="text-sm text-slate-500">Predicciones</p><p class="text-3xl font-bold mt-2">{{ Object.values(summary.predicciones).reduce((a,b)=>a+b,0) }}</p></div>
   <div class="rounded-xl bg-white dark:bg-slate-800 border border-red-200 dark:border-red-900 p-5"><p class="text-sm text-slate-500">Prioridad alta</p><p class="text-3xl font-bold mt-2 text-red-600">{{ summary.predicciones.ALTO||0 }}</p></div>
   <div class="rounded-xl bg-white dark:bg-slate-800 border border-amber-200 dark:border-amber-900 p-5"><p class="text-sm text-slate-500">Prioridad media</p><p class="text-3xl font-bold mt-2 text-amber-600">{{ summary.predicciones.MEDIO||0 }}</p></div>
   <div class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5"><p class="text-sm text-slate-500">Modelo</p><p class="text-sm font-semibold mt-2 break-all">{{ summary.modelo?.version||'—' }}</p><p class="text-xs text-slate-500 mt-1">Medio ≥ {{ summary.modelo?.umbral_medio }} · Alto ≥ {{ summary.modelo?.umbral_alto }} (propuesta)</p></div>
  </div>
  <div class="flex flex-wrap gap-3 mt-6">
   <select v-model="filter.estado" aria-label="Estado" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los estados</option><option v-for="[k,l] in states" :key="k" :value="k">{{ l }}</option></select>
   <select v-model="filter.gestion" @change="filter.curso=''" aria-label="Gestión" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todas las gestiones</option><option v-for="y in years" :key="y" :value="y">{{ y }}</option></select>
   <select v-model="filter.curso" aria-label="Curso" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los cursos</option><option v-for="[id,l] in courses" :key="id" :value="id">{{ l }}</option></select>
   <select v-model="filter.nivel" aria-label="Nivel" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los niveles</option><option value="ALTO">Alto (≥ 0,8)</option><option value="MEDIO">Medio (0,5 – 0,8)</option></select>
   <span class="self-center text-sm text-slate-500">{{ visible.length }} de {{ alerts.length }} alertas</span>
  </div>
  <div class="grid lg:grid-cols-5 gap-6 mt-4">
   <div class="lg:col-span-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
    <table class="w-full text-sm">
     <thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr><th class="p-3">Estudiante</th><th class="p-3">Gestión / curso</th><th class="p-3">Prioridad</th><th class="p-3">Estado</th><th class="p-3">Responsable</th><th class="p-3">Interv.</th></tr></thead>
     <tbody>
      <tr v-if="!visible.length"><td colspan="6" class="p-6 text-center text-slate-500">{{ busy ? 'Cargando…' : 'No hay alertas con estos filtros.' }}</td></tr>
      <tr v-for="a in visible" :key="a.id" @click="open(a)" class="border-t border-slate-100 dark:border-slate-700 cursor-pointer hover:bg-blue-50 dark:hover:bg-slate-700" :class="selected?.id===a.id?'bg-blue-50 dark:bg-slate-700':''">
       <td class="p-3 font-medium">{{ etiquetaCodigo(a.estudiante) }}</td>
       <td class="p-3">{{ a.gestion }} · {{ a.curso }}<span v-if="a.uso==='RETROSPECTIVO_EN_ENTRENAMIENTO'" class="block text-xs text-slate-500">Retrospectivo (usado en entrenamiento)</span><span v-else class="block text-xs text-blue-600">Cohorte actual</span></td>
       <td class="p-3"><span class="px-2 py-1 rounded-full text-xs font-semibold" :class="levelClass(a.nivel)">{{ a.nivel }}</span><span class="block text-xs text-slate-500 mt-1">Puesto {{ a.prioridad.puesto }} de {{ a.prioridad.de }}</span></td>
       <td class="p-3">{{ label(states,a.estado) }}</td>
       <td class="p-3 text-xs">{{ a.responsable.rol }}</td>
       <td class="p-3 text-center">{{ a.intervenciones }}</td>
      </tr>
     </tbody>
    </table>
   </div>
   <aside class="lg:col-span-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5">
    <p v-if="!selected" class="text-slate-500">Selecciona una alerta para ver sus factores, asignar responsable y registrar intervenciones.</p>
    <template v-else>
     <h2 class="font-semibold text-lg">{{ etiquetaCodigo(selected.estudiante) }} · {{ selected.curso }} · {{ selected.gestion }}</h2>
     <p class="text-sm text-slate-500">Corte {{ selected.fecha_corte }} · puntaje {{ score(selected.probabilidad) }} · puesto {{ selected.prioridad.puesto }} de {{ selected.prioridad.de }} en {{ selected.gestion }}</p>
     <p class="text-xs text-slate-500 mt-1">Ranking de prioridad, no riesgo absoluto.</p>
     <h3 class="font-semibold mt-4">Factores que más elevan la prioridad</h3>
     <ul class="mt-2 space-y-1 text-sm"><li v-for="f in selected.factores" :key="f.variable" class="flex justify-between"><span>{{ f.variable }} = {{ typeof f.valor==='number'&&f.valor<1&&f.valor>0 ? f.valor.toFixed(2) : f.valor }}</span><span class="text-slate-500">+{{ f.aporte }}</span></li><li v-if="!selected.factores.length" class="text-slate-500">Sin factores positivos.</li></ul>
     <h3 class="font-semibold mt-5">Responsable</h3>
     <select :value="selected.responsable.id" :disabled="busy" @change="assign($event.target.value)" aria-label="Responsable" class="mt-2 w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-1.5 text-sm">
      <option v-for="p in people" :key="p.id" :value="p.id">{{ p.nombre }} ({{ p.rol }})</option>
     </select>
     <h3 class="font-semibold mt-5">Estado</h3>
     <div class="flex flex-wrap gap-2 mt-2"><button v-for="[k,l] in states.filter(s=>s[0]!=='CERRADA')" :key="k" :disabled="busy||selected.estado===k" @click="setState(k)" class="px-3 py-1.5 rounded-lg border text-sm disabled:opacity-40">{{ l }}</button></div>
     <div class="flex gap-2 mt-2"><input v-model="closing" placeholder="Motivo de cierre (obligatorio)" class="flex-1 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-1.5 text-sm"><button :disabled="busy||!closing.trim()" @click="setState('CERRADA')" class="px-3 py-1.5 rounded-lg bg-slate-700 text-white text-sm disabled:opacity-40">Cerrar</button></div>
     <p v-if="selected.motivo_cierre" class="text-xs text-slate-500 mt-1">Cerrada: {{ selected.motivo_cierre }}</p>
     <h3 class="font-semibold mt-5">Recomendaciones pedagógicas <span class="text-xs font-normal text-slate-500">{{ recs?.version }}</span></h3>
     <p class="text-xs text-amber-700 dark:text-amber-300 mt-1">{{ recs?.validacion || 'Propuesta pendiente de validación con docentes y Dirección' }}.</p>
     <ul class="mt-2 space-y-2"><li v-for="r in recs?.reglas||[]" :key="r.codigo" class="rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm">
      <p><strong>{{ r.codigo }} · {{ r.nombre }}</strong></p><p class="mt-1">{{ r.recomendacion }}</p>
      <p class="text-xs text-slate-500 mt-1">Se activa porque: {{ r.dato }} · regla: {{ r.condicion }}</p>
      <button v-if="!r.intervencion_id" :disabled="busy||selected.estado==='CERRADA'" @click="adopt(r)" class="mt-2 px-2 py-1 rounded border border-blue-400 text-blue-700 dark:text-blue-300 text-xs disabled:opacity-40">Registrar como intervención</button>
      <p v-else class="mt-2 text-xs text-green-700 dark:text-green-400">Registrada como intervención.</p>
     </li></ul>
     <h3 class="font-semibold mt-5">Intervenciones</h3>
     <ul class="mt-2 space-y-3"><li v-for="i in items" :key="i.id" class="rounded-lg border border-slate-200 dark:border-slate-700 p-3 text-sm">
      <p>{{ i.recomendacion }}</p><p class="text-xs text-slate-500 mt-1">{{ label(stepStates,i.estado) }}<span v-if="i.fecha_planificada"> · planificada {{ i.fecha_planificada }}</span></p>
      <p v-if="i.accion_realizada" class="text-xs mt-1">Ejecutada {{ i.realizada_en?.slice(0,10) }}: {{ i.accion_realizada }}</p>
      <p v-if="i.resultado" class="text-xs mt-1">Resultado: {{ i.resultado }}</p>
      <form v-if="execution?.id===i.id" @submit.prevent="saveExecution" class="mt-2 space-y-2 rounded-lg bg-slate-50 dark:bg-slate-900 p-2">
       <div class="flex gap-2"><select v-model="execution.tipo_accion" aria-label="Tipo de acción" class="flex-1 rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-2 py-1 text-xs"><option v-for="(l,k) in recs?.tipos_accion" :key="k" :value="k">{{ l }}</option></select>
       <input v-model="execution.fecha_ejecucion" type="date" :max="today" required aria-label="Fecha de ejecución" class="rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-2 py-1 text-xs"></div>
       <textarea v-model="execution.accion_realizada" required rows="2" placeholder="Qué se hizo" class="w-full rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-2 py-1 text-xs"></textarea>
       <textarea v-model="execution.resultado" rows="2" placeholder="Resultado (opcional)" class="w-full rounded border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-2 py-1 text-xs"></textarea>
       <div class="flex gap-2"><button :disabled="busy" class="px-2 py-1 rounded bg-blue-600 text-white text-xs">Guardar ejecución</button><button type="button" @click="execution=null" class="px-2 py-1 rounded border text-xs">Cancelar</button></div>
      </form>
      <div class="flex flex-wrap gap-1 mt-2"><button v-for="[k,l] in stepStates.filter(s=>s[0]!==i.estado&&s[0]!=='PROPUESTA')" :key="k" :disabled="busy" @click="advance(i,k)" class="px-2 py-1 rounded border text-xs">{{ l }}</button></div>
     </li><li v-if="!items.length" class="text-sm text-slate-500">Aún no hay intervenciones.</li></ul>
     <form @submit.prevent="propose" class="mt-4 space-y-2">
      <textarea v-model="form.recomendacion" required minlength="3" rows="2" placeholder="Ej.: citar a la familia, tutoría de nivelación…" class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-2 text-sm"></textarea>
      <div class="flex gap-2"><input v-model="form.fecha_planificada" type="date" aria-label="Fecha planificada" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-1.5 text-sm"><button :disabled="busy||selected.estado==='CERRADA'" class="flex-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm disabled:opacity-40">Registrar intervención</button></div>
     </form>
     <h3 class="font-semibold mt-5">Historial (auditoría)</h3>
     <ol class="mt-2 space-y-2 text-xs"><li v-for="h in history" :key="h.id" class="border-l-2 border-slate-300 dark:border-slate-600 pl-2">
      <p class="text-slate-500">{{ h.registrado_en?.replace('T',' ') }} · {{ h.rol }} · {{ h.tabla==='alertas'?'Alerta':'Intervención' }}</p>
      <p v-for="c in changes(h)" :key="c">{{ c }}</p>
     </li><li v-if="!history.length" class="text-slate-500">Sin cambios registrados.</li></ol>
    </template>
   </aside>
  </div>
 </section>
</template>
