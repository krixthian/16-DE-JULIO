<script setup>
import { etiquetaCodigo } from '../utils/estudiante'
import { ref, computed, onMounted, nextTick } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js'
import api from '../services/api'
ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)
const alerts=ref([]),summary=ref(null),people=ref([]),selected=ref(null),items=ref([]),history=ref([]),recs=ref(null),busy=ref(false),error=ref(''),notice=ref('')
const why=ref(null),whyError=ref(''),showAll=ref(false),whySection=ref(null)
const tab=ref('modelo'),academic=ref(null),academicYear=ref('')
const academicRows=computed(()=>(academic.value?.casos||[]).filter(c=>!academicYear.value||c.gestion===Number(academicYear.value)))
const academicNew=computed(()=>academicRows.value.filter(c=>!c.modelo.alerta_id).length)
const pct0=v=>v==null?'—':`${Math.round(v*100)} %`
const dark=ref(document.documentElement.classList.contains('dark'))
const comma=(v,d=1)=>v==null?'—':Number(v).toFixed(d).replace('.',',')
const shown=computed(()=>why.value?(showAll.value?why.value.variables:why.value.variables.slice(0,8)):[])
const whyChart=computed(()=>{const v=(why.value?.variables||[]).filter(x=>x.efecto!=='neutro').slice(0,10);return {
 labels:v.map(x=>`${x.etiqueta}: ${x.valor_texto}`),
 datasets:[{label:'Aporte al puntaje',data:v.map(x=>x.aporte),backgroundColor:v.map(x=>x.aporte>0?'#d93b3b':'#1baf7a'),borderRadius:4,borderSkipped:false,maxBarThickness:22}]}})
const whyOptions=computed(()=>{const ink=dark.value?'#cbd5e1':'#475569',grid=dark.value?'rgba(148,163,184,.15)':'rgba(100,116,139,.15)';return {
 responsive:true,maintainAspectRatio:false,indexAxis:'y',animation:false,plugins:{legend:{display:false},
  tooltip:{callbacks:{label:c=>`${c.raw>0?'Eleva':'Reduce'} la prioridad (${c.raw>0?'+':''}${comma(c.raw,3)})`}}},
 scales:{x:{grid:{color:grid},border:{display:false},ticks:{color:ink},title:{display:true,text:'← reduce la prioridad · eleva la prioridad →',color:ink}},
  y:{grid:{display:false},ticks:{color:ink}}}}})
const gaugeLeft=v=>`${Math.min(100,Math.max(0,v*100))}%`
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
 try{const [a,s,p,ac]=await Promise.all([api.get('/alertas'),api.get('/alertas/resumen'),api.get('/alertas/responsables'),api.get('/alertas/academicas')]);alerts.value=a.data;summary.value=s.data;people.value=p.data;academic.value=ac.data}catch(e){error.value=message(e)}finally{busy.value=false}
}
async function loadDetail(){
 const id=selected.value.id
 const [i,h,r]=await Promise.all([api.get(`/alertas/${id}/intervenciones`),api.get(`/alertas/${id}/historial`),api.get(`/alertas/${id}/recomendaciones`)])
 items.value=i.data;history.value=h.data;recs.value=r.data
}
async function loadWhy(){
 why.value=null;whyError.value='';showAll.value=false
 try{why.value=(await api.get(`/alertas/${selected.value.id}/explicacion`)).data}catch(e){whyError.value=message(e)}
}
async function goWhy(){await nextTick();whySection.value?.scrollIntoView({behavior:'smooth',block:'start'})}
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
 loadWhy()
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
  <div class="flex flex-wrap gap-2 mt-6 border-b border-slate-200 dark:border-slate-700" role="tablist">
   <button role="tab" :aria-selected="tab==='modelo'" @click="tab='modelo'" class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab==='modelo'?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">Alertas del modelo ({{ alerts.length }})</button>
   <button role="tab" :aria-selected="tab==='academico'" @click="tab='academico'" class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab==='academico'?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">Riesgo académico por reglas ({{ academic?.total ?? '…' }})</button>
  </div>
  <section v-if="tab==='academico'&&academic" class="mt-4">
   <div class="rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-100 p-4 text-sm max-w-5xl">
    <strong>Qué muestra esta pestaña.</strong> {{ academic.criterio }}
    <span class="block mt-1">De {{ academic.total }} estudiantes con áreas bajo 51, <strong>{{ academic.sin_alerta_del_modelo }} no tienen alerta del modelo</strong>. Propuesta pendiente de validar con docentes y Dirección; vista de solo lectura.</span>
   </div>
   <div class="flex flex-wrap items-center gap-3 mt-4">
    <select v-model="academicYear" aria-label="Gestión" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todas las gestiones</option><option v-for="y in academic.gestiones" :key="y" :value="y">{{ y }}</option></select>
    <span class="text-sm text-slate-500">{{ academicRows.length }} estudiantes · {{ academicNew }} sin alerta del modelo</span>
   </div>
   <div class="mt-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
    <table class="w-full text-sm">
     <thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr><th class="p-3">Estudiante</th><th class="p-3">Gestión / curso</th><th class="p-3">Áreas con nota menor a 51</th><th class="p-3">Promedio T1</th><th class="p-3">Faltas / asistencia</th><th class="p-3">Modelo XGBoost</th><th class="p-3">Reglas</th></tr></thead>
     <tbody>
      <tr v-if="!academicRows.length"><td colspan="7" class="p-6 text-center text-slate-500">No hay estudiantes con áreas bajo 51 en esta gestión.</td></tr>
      <tr v-for="c in academicRows" :key="c.matricula_id" class="border-t border-slate-100 dark:border-slate-700 align-top">
       <td class="p-3 font-medium">{{ etiquetaCodigo(c.estudiante) }}</td>
       <td class="p-3">{{ c.gestion }} · {{ c.curso }}</td>
       <td class="p-3"><span class="font-semibold text-red-700 dark:text-red-300">{{ c.areas_bajo_51.length }} {{ c.areas_bajo_51.length===1?'área':'áreas' }}</span><span class="block text-xs text-slate-500">{{ c.areas_bajo_51.map(a=>`${a.area} ${a.nota}`).join(' · ') }}</span></td>
       <td class="p-3">{{ c.promedio_T1 }}</td>
       <td class="p-3">{{ c.faltas_T1 }} · {{ pct0(c.asistencia) }}</td>
       <td class="p-3"><span v-if="c.modelo.alerta_id" class="px-2 py-1 rounded-full text-xs font-semibold" :class="levelClass(c.modelo.nivel)">Alerta {{ c.modelo.nivel }}</span><span v-else class="text-slate-500">Sin alerta</span><span class="block text-xs text-slate-500 mt-1">puntaje {{ comma(c.modelo.puntaje,3) }}</span></td>
       <td class="p-3 text-xs">{{ c.reglas.join(' ') }}</td>
      </tr>
     </tbody>
    </table>
   </div>
   <p class="mt-3 text-xs text-slate-500 max-w-5xl">Por qué el modelo no los prioriza: el modelo aprende del historial de abandonos, y en ese historial los estudiantes con áreas bajo 51 casi no abandonaron. Esta regla complementa al modelo; no lo reemplaza.</p>
  </section>
  <div v-if="tab==='modelo'" class="flex flex-wrap gap-3 mt-4">
   <select v-model="filter.estado" aria-label="Estado" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los estados</option><option v-for="[k,l] in states" :key="k" :value="k">{{ l }}</option></select>
   <select v-model="filter.gestion" @change="filter.curso=''" aria-label="Gestión" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todas las gestiones</option><option v-for="y in years" :key="y" :value="y">{{ y }}</option></select>
   <select v-model="filter.curso" aria-label="Curso" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los cursos</option><option v-for="[id,l] in courses" :key="id" :value="id">{{ l }}</option></select>
   <select v-model="filter.nivel" aria-label="Nivel" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los niveles</option><option value="ALTO">Alto (≥ 0,8)</option><option value="MEDIO">Medio (0,5 – 0,8)</option></select>
   <span class="self-center text-sm text-slate-500">{{ visible.length }} de {{ alerts.length }} alertas</span>
  </div>
  <div v-if="tab==='modelo'" class="grid lg:grid-cols-5 gap-6 mt-4">
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
     <h3 class="font-semibold mt-4">¿Por qué esta alerta?</h3>
     <p v-if="why" class="mt-1 text-sm">{{ why.resumen }}</p>
     <p v-else-if="whyError" class="mt-1 text-sm text-red-600">{{ whyError }}</p>
     <p v-else class="mt-1 text-sm text-slate-500">Calculando la explicación…</p>
     <button v-if="why" @click="goWhy" class="mt-2 text-sm text-blue-700 dark:text-blue-300 underline">Ver la explicación completa ↓</button>
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
  <section v-if="tab==='modelo'&&selected&&why" ref="whySection" class="mt-6 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5">
   <div class="flex flex-wrap items-baseline justify-between gap-2">
    <h2 class="text-xl font-semibold">¿Por qué {{ etiquetaCodigo(selected.estudiante) }} tiene prioridad {{ why.nivel.nivel==='ALTO'?'alta':'media' }}?</h2>
    <span class="text-sm text-slate-500">{{ why.curso }} · {{ why.gestion }} · comparado con {{ why.estudiantes_en_curso }} estudiantes del curso</span>
   </div>
   <div class="grid lg:grid-cols-3 gap-6 mt-4">
    <div class="lg:col-span-1 space-y-4">
     <div class="rounded-lg bg-slate-50 dark:bg-slate-900 p-4">
      <p class="text-sm font-semibold">1. Por qué está en este nivel</p>
      <div class="relative mt-6 h-3 rounded-full bg-gradient-to-r from-slate-200 via-amber-200 to-red-300 dark:from-slate-700 dark:via-amber-800 dark:to-red-800" aria-hidden="true">
       <span class="absolute -top-5 text-[10px] text-slate-500 -translate-x-1/2" :style="{left:gaugeLeft(why.nivel.umbral_medio)}">medio {{ comma(why.nivel.umbral_medio) }}</span>
       <span class="absolute -top-5 text-[10px] text-slate-500 -translate-x-1/2" :style="{left:gaugeLeft(why.nivel.umbral_alto)}">alto {{ comma(why.nivel.umbral_alto) }}</span>
       <i class="absolute top-0 h-3 w-px bg-slate-500" :style="{left:gaugeLeft(why.nivel.umbral_medio)}"></i>
       <i class="absolute top-0 h-3 w-px bg-slate-500" :style="{left:gaugeLeft(why.nivel.umbral_alto)}"></i>
       <i class="absolute -top-1 h-5 w-5 rounded-full border-2 border-white dark:border-slate-900 -translate-x-1/2" :class="why.nivel.nivel==='ALTO'?'bg-red-600':'bg-amber-500'" :style="{left:gaugeLeft(why.nivel.puntaje)}"></i>
      </div>
      <p class="mt-3 text-sm">{{ why.nivel.motivo }}</p>
      <p class="mt-2 text-xs text-slate-500">{{ why.nivel.nota }}</p>
     </div>
     <div class="rounded-lg bg-slate-50 dark:bg-slate-900 p-4">
      <p class="text-sm font-semibold">2. En palabras</p>
      <p class="mt-2 text-sm">{{ why.resumen }}</p>
      <p v-if="why.areas_en_desarrollo.length" class="mt-2 text-sm text-red-700 dark:text-red-300">Áreas en desarrollo (&lt; 51): {{ why.areas_en_desarrollo.map(a=>`${a.etiqueta} (${a.valor})`).join(', ') }}.</p>
      <p v-else class="mt-2 text-xs text-slate-500">Ninguna área por debajo de 51.</p>
     </div>
    </div>
    <div class="lg:col-span-2">
     <p class="text-sm font-semibold">3. Qué eleva y qué reduce la prioridad (10 variables con más peso)</p>
     <div class="mt-2 h-80"><Bar :data="whyChart" :options="whyOptions" aria-label="Aporte de cada variable a la prioridad" /></div>
    </div>
   </div>
   <p class="text-sm font-semibold mt-6">4. Todas las variables comparadas con su curso</p>
   <div class="overflow-x-auto mt-2">
    <table class="w-full text-sm">
     <thead class="text-left text-slate-500"><tr><th class="py-2 pr-3">Variable</th><th class="py-2 pr-3">Estudiante</th><th class="py-2 pr-3">Promedio del curso</th><th class="py-2 pr-3">Efecto en la prioridad</th><th class="py-2 pr-3 text-right">Aporte</th></tr></thead>
     <tbody>
      <tr v-for="v in shown" :key="v.variable" class="border-t border-slate-100 dark:border-slate-700">
       <td class="py-2 pr-3">{{ v.etiqueta }}<span class="block text-xs text-slate-400">{{ v.grupo }}</span></td>
       <td class="py-2 pr-3 font-medium">{{ v.valor_texto }}</td>
       <td class="py-2 pr-3 text-slate-500">{{ v.comparacion?.replace('curso: ','')||'—' }}</td>
       <td class="py-2 pr-3"><span v-if="v.efecto==='sube'" class="text-red-700 dark:text-red-300">▲ eleva<span v-if="v.peso_relativo"> ({{ comma(v.peso_relativo,0) }} % de lo que la eleva)</span></span><span v-else-if="v.efecto==='baja'" class="text-emerald-700 dark:text-emerald-300">▼ reduce</span><span v-else class="text-slate-400">sin efecto</span></td>
       <td class="py-2 pr-3 text-right tabular-nums">{{ v.aporte>0?'+':'' }}{{ comma(v.aporte,3) }}</td>
      </tr>
     </tbody>
    </table>
   </div>
   <button @click="showAll=!showAll" class="mt-2 text-sm text-blue-700 dark:text-blue-300 underline">{{ showAll?'Ver solo las 8 principales':`Ver las ${why.variables.length} variables` }}</button>
   <details class="mt-4 text-xs text-slate-500">
    <summary class="cursor-pointer">Cómo se calcula y advertencias</summary>
    <p class="mt-2">{{ why.metodo }} Punto de partida: {{ comma(why.punto_partida,3) }} → puntaje con sus datos: {{ comma(why.puntaje_recalculado,3) }}<span v-if="why.coincide_con_guardado"> (coincide con el puntaje guardado).</span></p>
    <p class="mt-1">{{ why.advertencia }}</p>
   </details>
  </section>
 </section>
</template>
