<script setup>
import { etiquetaCodigo } from '../utils/estudiante'
import { ref, computed, onMounted, nextTick } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js'
import api from '../services/api'
import AyudaPantalla from '../components/AyudaPantalla.vue'
import PerfilRiesgo from '../components/PerfilRiesgo.vue'
ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)
const alerts=ref([]),summary=ref(null),people=ref([]),selected=ref(null),items=ref([]),history=ref([]),recs=ref(null),busy=ref(false),error=ref(''),notice=ref('')
const why=ref(null),whyError=ref(''),showAll=ref(false),showModel=ref(false),whySection=ref(null)
const tab=ref('seguimiento'),academic=ref(null),academicYear=ref(''),absence=ref(null),absenceDays=ref(5)
const follow=ref(null),followYear=ref(''),followDate=ref(''),followLevel=ref('riesgo')
async function loadFollow(){try{const params={};if(followYear.value)params.gestion=followYear.value;if(followDate.value)params.fecha=followDate.value
 follow.value=(await api.get('/alertas/seguimiento',{params,timeout:30000})).data;if(follow.value.casos_abiertos_ahora)reloadCases();if(!followYear.value)followYear.value=follow.value.gestion;if(!followDate.value)followDate.value=follow.value.fecha}catch(e){error.value=message(e)}}
const followReason=ref('')
const followRows=computed(()=>(follow.value?.alertas||[]).filter(a=>(followLevel.value==='todos'||followLevel.value===a.perfil.nivel||followLevel.value==='riesgo'&&a.perfil.nivel!=='VERDE')&&(!followReason.value||a.perfil.motivos.some(x=>x.dimension===followReason.value))))
const cuenta=computed(()=>{const c={URGENTE:0,ROJO:0,AMARILLO:0,VERDE:0};for(const a of follow.value?.alertas||[])c[a.perfil.nivel]++;return c})
const NIVEL={URGENTE:['Urgente','bg-red-700 text-white'],ROJO:['Rojo','bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'],AMARILLO:['Amarillo','bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'],VERDE:['Verde','bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200']}
const fechaCorta=f=>f?f.split('-').reverse().join('/'):'—'
const scope=ref('gestion'),byYear=ref(null)
async function loadByYear(){try{byYear.value=(await api.get('/alertas/seguimiento/gestiones',{timeout:30000})).data}catch(e){error.value=message(e)}}
const tarjetas=computed(()=>[
 {v:'riesgo',l:'Con alerta',n:followCount.value,d:`de ${follow.value?.total} estudiantes`},
 {v:'URGENTE',l:'Urgente',n:cuenta.value.URGENTE,c:'text-red-700 dark:text-red-400',punto:'bg-red-700',d:`${follow.value?.racha_alerta} o más faltas seguidas`},
 {v:'ROJO',l:'Rojo',n:cuenta.value.ROJO,c:'text-red-600',punto:'bg-red-500',d:'Atender pronto'},
 {v:'AMARILLO',l:'Amarillo',n:cuenta.value.AMARILLO,c:'text-amber-600',punto:'bg-amber-400',d:'Observar'},
 {v:'VERDE',l:'Verde',n:cuenta.value.VERDE,c:'text-emerald-600',punto:'bg-emerald-500',d:'Sin alerta'}])
const followCount=computed(()=>(follow.value?.alertas||[]).filter(a=>a.perfil.nivel!=='VERDE').length)
const monthName={feb:'febrero',mar:'marzo',abr:'abril',may:'mayo',jun:'junio',jul:'julio',ago:'agosto',sep:'septiembre',oct:'octubre'}
const factorValue=f=>f.valor==null?'sin dato':f.variable.startsWith('prop')?`${comma(f.valor*100,1)} %`:f.variable==='tendencia_faltas'?(f.valor>0?'en aumento':f.valor<0?'en descenso':'estable'):Number.isInteger(f.valor)?f.valor:comma(f.valor,1)
const factorText=f=>`${f.descripcion}: ${factorValue(f)}`
async function loadAbsence(){try{const params={dias:absenceDays.value};if(followYear.value)params.gestion=followYear.value;absence.value=(await api.get('/alertas/inasistencia',{params})).data}catch(e){error.value=message(e)}}
const academicRows=computed(()=>(academic.value?.casos||[]).filter(c=>!academicYear.value||c.gestion===Number(academicYear.value)))
const academicNew=computed(()=>academicRows.value.filter(c=>!c.caso).length)
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
 &&(!filter.value.curso||a.curso_id===Number(filter.value.curso))&&(!filter.value.nivel||(a.nivel_alerta||a.nivel)===filter.value.nivel)))
const levelClass=n=>n==='ALTO'?'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200':n==='MEDIO'?'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200':'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
const caseClass=t=>t==='actual'?'border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40 text-blue-900 dark:text-blue-100':'border-slate-300 dark:border-slate-600 bg-slate-100 dark:bg-slate-900 text-slate-800 dark:text-slate-200'
const modelInfo=v=>{const m=/^xgb-(.+)-(\d{4})(\d{2})(\d{2})\d{6}$/.exec(v||'');return m?`Versión ${m[1]} · entrenado el ${m[4]}/${m[3]}/${m[2]}`:(v||'—')}
const gaugeZones=(medio,alto)=>{const a=gaugeLeft(medio),b=gaugeLeft(alto);return {background:`linear-gradient(to right,#34d399 0 ${a},#fbbf24 ${a} ${b},#f87171 ${b} 100%)`}}
const fields={estado:'Estado',responsable_id:'Responsable',motivo_cierre:'Motivo de cierre',accion_realizada:'Acción',resultado:'Resultado'}
const who=id=>people.value.find(p=>p.id===id)?.nombre||`Usuario ${id}`
const show=(k,v)=>v==null?'—':k==='responsable_id'?who(v):k==='estado'?label([...states,...stepStates],v):v
const changes=h=>h.antes?Object.keys(fields).filter(k=>k in h.despues&&h.antes[k]!==h.despues[k]).map(k=>`${fields[k]}: ${show(k,h.antes[k])} → ${show(k,h.despues[k])}`):[h.motivo]
async function load(){
 busy.value=true;error.value=''
 try{const [a,s,p,ac]=await Promise.all([api.get('/alertas'),api.get('/alertas/resumen'),api.get('/alertas/responsables'),api.get('/alertas/academicas')]);alerts.value=a.data;summary.value=s.data;people.value=p.data;academic.value=ac.data;loadFollow().then(loadAbsence)}catch(e){error.value=message(e)}finally{busy.value=false}
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
async function openCase(a){
 busy.value=true;error.value='';notice.value=''
 try{const r=(await api.post('/alertas/seguimiento/abrir',{matricula_id:a.matricula_id,gestion:follow.value.gestion,fecha:follow.value.fecha},{timeout:30000})).data
  a.caso={id:r.alerta_id,estado:r.alerta.estado};await reloadCases();notice.value=r.nuevo?`Caso abierto para ${etiquetaCodigo(a.estudiante)}. Ya puedes asignar responsable e intervenciones.`:'Este estudiante ya tenía un caso abierto.'}
 catch(e){error.value=message(e)}finally{busy.value=false}
}
async function reloadCases(){try{alerts.value=(await api.get('/alertas')).data}catch(e){error.value=message(e)}}
async function viewCase(id){tab.value='modelo';if(!alerts.value.some(x=>x.id===id))await reloadCases();const a=alerts.value.find(x=>x.id===id);if(a)open(a)}
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
  <p class="mt-2 text-slate-500 dark:text-slate-400">A quién apoyar primero, según sus notas, actitud y asistencia. Es una guía: no predice quién abandonará.<span v-if="follow?.alertas?.some(a=>a.origen==='SIMULADO')" class="ml-2 px-2 py-0.5 rounded-full text-xs bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200">Gestión {{ follow.gestion }}: datos simulados</span></p>
  <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }}</div>
  <div v-if="notice" class="mt-6 bg-green-50 text-green-800 rounded-xl p-4">{{ notice }}</div>
  <div class="mt-6 inline-flex rounded-lg border border-slate-300 dark:border-slate-600 p-1 text-sm" role="group" aria-label="Alcance del resumen">
   <button v-for="[v,l] in [['gestion','Esta gestión'],['todas','Todas las gestiones']]" :key="v" @click="scope=v;if(v==='todas'&&!byYear)loadByYear()" class="px-4 py-1.5 rounded-md font-medium" :class="scope===v?'bg-blue-600 text-white':'text-slate-600 dark:text-slate-300'" :aria-pressed="scope===v">{{ l }}</button>
  </div>
  <section v-if="scope==='todas'" class="mt-4">
   <p v-if="!byYear" class="text-sm text-slate-500">Calculando el resumen de todas las gestiones…</p>
   <div v-else class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
    <table class="w-full text-sm"><thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr>
     <th class="px-4 py-2.5">Gestión</th><th class="px-4 py-2.5 text-right">Estudiantes</th><th class="px-4 py-2.5 text-right">Alertas inmediatas en el año</th>
     <th class="px-4 py-2.5 text-right">Abandonos confirmados</th><th class="px-4 py-2.5 text-right">Detectados</th><th class="px-4 py-2.5 text-right">Falsas alarmas</th></tr></thead>
     <tbody>
      <tr v-for="g in byYear.gestiones" :key="g.gestion" class="border-t border-slate-100 dark:border-slate-700">
       <td class="px-4 py-2.5 font-medium">{{ g.gestion }}<span v-if="g.simulada" class="ml-1 text-xs text-slate-400">(simulado)</span><span v-if="g.en_curso" class="ml-2 text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200">en curso</span></td>
       <td class="px-4 py-2.5 text-right tabular-nums">{{ g.matriculas }}</td>
       <td class="px-4 py-2.5 text-right tabular-nums font-semibold text-red-700 dark:text-red-400">{{ g.alertas_inmediatas }}</td>
       <td class="px-4 py-2.5 text-right tabular-nums">{{ g.abandonos_confirmados ?? '—' }}</td>
       <td class="px-4 py-2.5 text-right tabular-nums">{{ g.detectados ?? '—' }}</td>
       <td class="px-4 py-2.5 text-right tabular-nums">{{ g.falsas_alarmas ?? '—' }}</td></tr>
      <tr class="border-t-2 border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-900 font-semibold">
       <td class="px-4 py-2.5">Total {{ Math.min(...byYear.total_reales.gestiones) }}-{{ Math.max(...byYear.total_reales.gestiones) }} (archivos recibidos, origen no verificado)</td>
       <td class="px-4 py-2.5 text-right tabular-nums">{{ byYear.total_reales.matriculas }}</td>
       <td class="px-4 py-2.5 text-right tabular-nums text-red-700 dark:text-red-400">{{ byYear.total_reales.alertas_inmediatas }}</td>
       <td class="px-4 py-2.5 text-right tabular-nums">{{ byYear.total_reales.abandonos_confirmados }}</td>
       <td class="px-4 py-2.5 text-right tabular-nums">{{ byYear.total_reales.detectados }} de {{ byYear.total_reales.abandonos_confirmados }}</td>
       <td class="px-4 py-2.5 text-right tabular-nums">{{ byYear.total_reales.falsas_alarmas }}</td></tr>
     </tbody></table>
   </div>
   <AyudaPantalla v-if="byYear" class="mt-3"><p>{{ byYear.nota }} En las gestiones en curso todavía no se sabe quién abandonó.</p></AyudaPantalla>
  </section>
  <div v-if="follow&&scope==='gestion'" class="grid grid-cols-2 lg:grid-cols-5 gap-4 mt-6">
   <button v-for="k in tarjetas" :key="k.v" @click="followLevel=k.v;followReason='';tab='seguimiento'" :aria-pressed="followLevel===k.v" class="text-left rounded-xl bg-white dark:bg-slate-800 border p-5 hover:shadow-md" :class="followLevel===k.v?'border-blue-500 ring-1 ring-blue-500':'border-slate-200 dark:border-slate-700'">
    <span class="text-sm text-slate-500 flex items-center gap-1.5"><span v-if="k.punto" class="inline-block h-2.5 w-2.5 rounded-full" :class="k.punto" aria-hidden="true"></span>{{ k.l }}</span>
    <span class="block text-3xl font-bold mt-2" :class="k.c">{{ k.n }}</span><span class="block text-xs text-slate-500 mt-1">{{ k.d }}</span>
   </button>
  </div>
  <div class="flex flex-wrap gap-2 mt-6 border-b border-slate-200 dark:border-slate-700" role="tablist">
   <button role="tab" :aria-selected="tab==='seguimiento'" @click="tab='seguimiento'" class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab==='seguimiento'?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">Alertas ({{ follow ? followCount : '…' }})</button>
   <button role="tab" :aria-selected="tab==='modelo'" @click="tab='modelo'" class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab==='modelo'?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">Casos abiertos ({{ alerts.length }})</button>
   <button role="tab" :aria-selected="tab==='academico'" @click="tab='academico'" class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab==='academico'?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">Notas bajas ({{ academic?.total ?? '…' }})</button>
   <button role="tab" :aria-selected="tab==='inasistencia'" @click="tab='inasistencia'" class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab==='inasistencia'?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">Faltas seguidas ({{ absence?.total ?? '…' }})</button>
  </div>
  <section v-if="tab==='seguimiento'&&follow" class="mt-4">
   <div class="flex flex-wrap items-end gap-3">
    <label class="text-sm font-medium">Gestión<input v-model.number="followYear" type="number" min="2000" max="2100" @change="followDate='';loadFollow();loadAbsence()" class="block mt-1 w-28 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"></label>
    <label class="text-sm font-medium">Fecha<input v-model="followDate" type="date" @change="loadFollow" class="block mt-1 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"></label>
    <label class="text-sm font-medium">Mostrar<select v-model="followLevel" class="block mt-1 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="riesgo">Todas las alertas</option><option v-for="n in ['URGENTE','ROJO','AMARILLO','VERDE']" :key="n" :value="n">{{ NIVEL[n][0] }}</option><option value="todos">Todos, incluido verde</option></select></label>
    <label class="text-sm font-medium">Motivo<select v-model="followReason" class="block mt-1 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Cualquiera</option><option v-for="d in ['Académica','Desempeño','Actitud','Asistencia','Modelo XGBoost']" :key="d">{{ d }}</option></select></label>
    <span class="text-sm text-slate-500 pb-2">{{ followRows.length }} estudiante(s)<template v-if="!follow.notas_t1_incluidas"> · las notas aparecen al cerrar el 1.er trimestre</template></span>
   </div>
   <AyudaPantalla class="mt-3" titulo="¿Cómo se lee esta lista?">
    <p><strong>Urgente</strong>: {{ follow.racha_alerta }} o más faltas seguidas. <strong>Rojo</strong> y <strong>amarillo</strong>: por notas, actitud o asistencia; en rojo van primero quienes tienen notas y asistencia a la vez. <strong>Verde</strong>: sin alerta. Solo se muestran las dimensiones con problema. Asistencia incluye la de cada materia; Académica y Actitud, las citaciones. «PB» es un estudiante de prueba.</p>
    <p><strong>Regla propuesta.</strong> {{ follow.nota_perfil }}</p>
    <p><strong>Puntaje de XGBoost</strong> ({{ monthName[follow.mes] || '—' }}): ordena dentro de cada nivel. {{ summary?.nota || 'No está calibrado: no es un riesgo absoluto.' }}</p>
    <details class="text-xs"><summary class="cursor-pointer">Detalle técnico del modelo y de la regla de faltas</summary>
     <p class="mt-1">Regla de faltas: en los archivos recibidos de 2021-2025 (origen no verificado) se cumplió en 11 de 11 abandonos; es una revisión de datos pasados y el abandono se definió con la propia asistencia.</p>
     <p v-if="follow.validacion_del_corte" class="mt-1">Modelo en este corte, con los archivos recibidos, de origen no verificado: AP {{ comma(follow.validacion_del_corte.xgboost.average_precision,2) }} frente a {{ comma(follow.validacion_del_corte.azar,3) }} del azar; detecta en promedio {{ comma(follow.validacion_del_corte.xgboost.verdaderos_positivos,1) }} de {{ follow.validacion_del_corte.abandonos }} abandonos con {{ comma(follow.validacion_del_corte.xgboost.falsos_positivos,1) }} falsas alarmas entre {{ follow.validacion_del_corte.matriculas }} matrículas. Puntajes: {{ follow.modelo_usado }}.</p>
    </details>
   </AyudaPantalla>
   <div class="mt-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
    <table class="w-full text-sm"><thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr><th class="px-3 py-2.5">N.º</th><th class="px-3 py-2.5">Estudiante</th><th class="px-3 py-2.5">Curso</th><th class="px-3 py-2.5">Alerta</th><th class="px-3 py-2.5">Motivo</th><th class="px-3 py-2.5">Faltas seguidas</th><th class="px-3 py-2.5">Puntaje</th><th class="px-3 py-2.5">Caso</th></tr></thead>
     <tbody><tr v-for="a in followRows" :key="a.matricula_id" class="border-t border-slate-100 dark:border-slate-700 align-middle">
      <td class="px-3 py-2.5 tabular-nums">{{ a.puesto }}</td>
      <td class="px-3 py-2.5 font-medium whitespace-nowrap">{{ etiquetaCodigo(a.estudiante) }}</td>
      <td class="px-3 py-2.5 whitespace-nowrap">{{ a.curso }}</td>
      <td class="px-3 py-2.5 whitespace-nowrap"><span class="px-2 py-1 rounded-full text-xs font-semibold" :class="NIVEL[a.perfil.nivel][1]">{{ NIVEL[a.perfil.nivel][0] }}</span><span v-if="a.perfil.notas_y_asistencia" class="block mt-1 w-fit px-2 py-0.5 rounded-full border border-red-300 dark:border-red-800 text-[11px] text-red-800 dark:text-red-200">Notas y asistencia</span></td>
      <td class="px-3 py-2.5"><PerfilRiesgo solo-alertas :colores="a.perfil.colores" /><p v-if="a.perfil.por_materia" class="mt-1 text-xs text-slate-500">{{ a.perfil.por_materia }}</p><p v-if="a.perfil.motivos.some(x=>x.dimension==='Modelo XGBoost')" class="text-xs text-slate-500">Solo el modelo</p></td>
      <td class="px-3 py-2.5 tabular-nums">{{ a.racha_actual }}<span v-if="a.racha_actual" class="block text-xs text-slate-500 whitespace-nowrap">{{ a.ultima_asistencia ? `última vez: ${fechaCorta(a.ultima_asistencia)}` : 'Sin asistencia' }}</span></td>
      <td class="px-3 py-2.5 text-xs tabular-nums"><details v-if="a.factores.length"><summary class="cursor-pointer">{{ comma(a.probabilidad,2) }}</summary><ul class="mt-1 space-y-0.5 text-slate-600 dark:text-slate-300"><li v-for="f in a.factores" :key="f.variable">{{ factorText(f) }}</li></ul></details><template v-else>{{ comma(a.probabilidad,2) }}</template></td>
      <td class="px-3 py-2.5 whitespace-nowrap"><button v-if="a.caso" @click="viewCase(a.caso.id)" class="text-xs px-3 py-1.5 rounded-lg border border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-950">Ver caso · {{ label(states,a.caso.estado) }}</button>
       <button v-else-if="follow.gestion===follow.gestion_en_curso" @click="openCase(a)" :disabled="busy" class="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">Abrir caso</button>
       <span v-else class="text-xs text-slate-400">Gestión pasada</span></td></tr>
      <tr v-if="!followRows.length"><td colspan="8" class="p-6 text-center text-slate-500">{{ follow.motivo || 'Ningún estudiante con alerta a esta fecha.' }}</td></tr></tbody></table>
   </div>
  </section>
  <section v-if="tab==='inasistencia'&&absence" class="mt-4">
   <p class="text-sm text-slate-500">Estudiantes con {{ absence.dias }} o más faltas seguidas al último día registrado de {{ absence.gestion }}.</p>
   <AyudaPantalla class="mt-2"><p>Cuenta la asistencia diaria o por materia: un día es falta si faltó a todas sus horas.</p><p>{{ absence.nota }}</p></AyudaPantalla>
   <div class="flex flex-wrap items-end gap-3 mt-4">
    <label class="text-sm font-medium">Faltas seguidas<select v-model.number="absenceDays" @change="loadAbsence" class="block mt-1 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option v-for="d in [3,5,10]" :key="d" :value="d">{{ d }} o más{{ d===5?' (regla propuesta)':'' }}</option></select></label>
    <span class="text-sm text-slate-500 pb-2">{{ absence.total }} estudiante(s)</span>
   </div>
   <div class="mt-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
    <table class="w-full text-sm"><thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr><th class="px-3 py-2.5">Estudiante</th><th class="px-3 py-2.5">Curso</th><th class="px-3 py-2.5">Faltas seguidas</th><th class="px-3 py-2.5">Desde</th><th class="px-3 py-2.5">Última asistencia</th></tr></thead>
     <tbody><tr v-for="a in absence.alertas" :key="a.matricula_id" class="border-t border-slate-100 dark:border-slate-700">
      <td class="px-3 py-2.5 font-medium whitespace-nowrap">{{ etiquetaCodigo(a.estudiante) }}</td><td class="px-3 py-2.5 whitespace-nowrap">{{ a.curso }} · {{ a.gestion }}</td>
      <td class="px-3 py-2.5"><span class="px-2 py-1 rounded-full text-xs font-semibold" :class="a.racha>=10?levelClass('ALTO'):levelClass('MEDIO')">{{ a.racha }} días</span></td>
      <td class="px-3 py-2.5">{{ a.desde }}</td><td class="px-3 py-2.5">{{ a.ultima_asistencia || 'Sin asistencia registrada' }}</td></tr>
      <tr v-if="!absence.alertas.length"><td colspan="5" class="p-6 text-center text-slate-500">Ningún estudiante tiene {{ absence.dias }} o más faltas seguidas en la asistencia registrada en el sistema.</td></tr></tbody></table>
   </div>
  </section>
  <section v-if="tab==='academico'&&academic" class="mt-4">
   <p class="text-sm text-slate-500">Estudiantes con alguna área bajo 51, para reforzamiento. {{ academic.sin_caso }} de {{ academic.total }} no tienen un caso abierto.</p>
   <AyudaPantalla class="mt-2"><p>{{ academic.criterio }}</p><p>Propuesta pendiente de validar con docentes y Dirección; vista de solo lectura.</p><p>No es alerta de abandono: en el historial, los estudiantes con áreas bajo 51 casi no abandonaron. Complementa al seguimiento; no lo reemplaza.</p></AyudaPantalla>
   <div class="flex flex-wrap items-center gap-3 mt-4">
    <select v-model="academicYear" aria-label="Gestión" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todas las gestiones</option><option v-for="y in academic.gestiones" :key="y" :value="y">{{ y }}</option></select>
    <span class="text-sm text-slate-500">{{ academicRows.length }} estudiantes · {{ academicNew }} sin caso abierto</span>
   </div>
   <div class="mt-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
    <table class="w-full text-sm">
     <thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr><th class="p-3">Estudiante<span v-if="academicRows.some(x=>x.origen==='SIMULADO')" class="ml-2 text-xs font-normal text-slate-500">PB: datos de prueba</span></th><th class="p-3">Gestión / curso</th><th class="p-3">Áreas con nota menor a 51</th><th class="p-3">Promedio T1</th><th class="p-3">Caso</th><th class="p-3">Reglas</th></tr></thead>
     <tbody>
      <tr v-if="!academicRows.length"><td colspan="6" class="p-6 text-center text-slate-500">No hay estudiantes con áreas bajo 51 en esta gestión.</td></tr>
      <tr v-for="c in academicRows" :key="c.matricula_id" class="border-t border-slate-100 dark:border-slate-700 align-top">
       <td class="p-3 font-medium">{{ etiquetaCodigo(c.estudiante) }}</td>
       <td class="p-3">{{ c.gestion }} · {{ c.curso }}</td>
       <td class="p-3"><span class="font-semibold text-red-700 dark:text-red-300">{{ c.areas_bajo_51.length }} {{ c.areas_bajo_51.length===1?'área':'áreas' }}</span><span class="block text-xs text-slate-500">{{ c.areas_bajo_51.map(a=>`${a.area} ${a.nota}`).join(' · ') }}</span></td>
       <td class="p-3">{{ c.promedio_T1 }}</td>
       <td class="p-3"><button v-if="c.caso" @click="viewCase(c.caso.id)" class="text-xs px-3 py-1.5 rounded-lg border border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300">Ver caso · {{ label(states,c.caso.estado) }}</button><span v-else class="text-xs text-slate-500">Sin caso</span></td>
       <td class="p-3 text-xs">{{ c.reglas.join(' ') }}</td>
      </tr>
     </tbody>
    </table>
   </div>
  </section>
  <div v-if="tab==='modelo'" class="flex flex-wrap gap-3 mt-4">
   <select v-model="filter.estado" aria-label="Estado" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los estados</option><option v-for="[k,l] in states" :key="k" :value="k">{{ l }}</option></select>
   <select v-model="filter.gestion" @change="filter.curso=''" aria-label="Gestión" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todas las gestiones</option><option v-for="y in years" :key="y" :value="y">{{ y }}</option></select>
   <select v-model="filter.curso" aria-label="Curso" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los cursos</option><option v-for="[id,l] in courses" :key="id" :value="id">{{ l }}</option></select>
   <select v-model="filter.nivel" aria-label="Nivel" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los niveles</option><option v-for="n in ['URGENTE','ROJO','AMARILLO']" :key="n" :value="n">{{ NIVEL[n][0] }}</option></select>
   <span class="self-center text-sm text-slate-500">{{ visible.length }} de {{ alerts.length }} casos</span>
  </div>
  <div v-if="tab==='modelo'" class="grid lg:grid-cols-3 gap-6 mt-4">
   <div class="lg:col-span-2 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
    <table class="w-full text-sm">
     <thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr><th class="px-3 py-2.5">Estudiante</th><th class="px-3 py-2.5">Curso</th><th class="px-3 py-2.5">Alerta</th><th class="px-3 py-2.5">Estado</th></tr></thead>
     <tbody>
      <tr v-if="!visible.length"><td colspan="4" class="p-6 text-center text-slate-500">{{ busy ? 'Cargando…' : 'No hay casos con estos filtros.' }}</td></tr>
      <tr v-for="a in visible" :key="a.id" @click="open(a)" class="border-t border-slate-100 dark:border-slate-700 cursor-pointer hover:bg-blue-50 dark:hover:bg-slate-700" :class="selected?.id===a.id?'bg-blue-50 dark:bg-slate-700':''">
       <td class="px-3 py-2.5 font-medium whitespace-nowrap">{{ etiquetaCodigo(a.estudiante) }}</td>
       <td class="px-3 py-2.5"><span class="whitespace-nowrap">{{ a.curso }} · {{ a.gestion }}</span><span v-if="a.uso==='RETROSPECTIVO_EN_ENTRENAMIENTO'" class="block text-xs text-slate-500">{{ a.abandono_confirmado ? 'Histórico · abandonó' : 'Histórico · no abandonó' }}</span><span v-else class="block text-xs text-blue-600">Gestión actual</span></td>
       <td class="px-3 py-2.5"><span class="px-2 py-1 rounded-full text-xs font-semibold" :class="NIVEL[a.nivel_alerta]?.[1]||levelClass(a.nivel)">{{ NIVEL[a.nivel_alerta]?.[0]||a.nivel }}</span></td>
       <td class="px-3 py-2.5"><span class="whitespace-nowrap">{{ label(states,a.estado) }}</span><span class="block text-xs text-slate-500 whitespace-nowrap" :title="`Responsable: ${a.responsable.nombre}`">{{ a.intervenciones }} interv.</span></td>
      </tr>
     </tbody>
    </table>
   </div>
   <aside class="lg:col-span-1 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5">
    <p v-if="!selected" class="text-slate-500">Selecciona una alerta para ver sus factores, asignar responsable y registrar intervenciones.</p>
    <template v-else>
     <h2 class="font-semibold text-lg">{{ etiquetaCodigo(selected.estudiante) }} · {{ selected.curso }} · {{ selected.gestion }}</h2>
     <div v-if="why" class="mt-3 rounded-lg border p-3 text-sm" :class="caseClass(why.caso.tipo)"><strong>{{ why.caso.titulo }}</strong> {{ why.caso.texto }}</div>
     <h3 class="font-semibold mt-4">¿Por qué?</h3>
     <p v-if="why" class="mt-1 text-sm">{{ why.resumen }}</p>
     <p v-else-if="whyError" class="mt-1 text-sm text-red-600">{{ whyError }}</p>
     <p v-else class="mt-1 text-sm text-slate-500">Calculando la explicación…</p>
     <button v-if="why" @click="goWhy" class="mt-2 text-sm text-blue-700 dark:text-blue-300 underline">Ver más ↓</button>
     <h3 class="font-semibold mt-5">Responsable</h3>
     <select :value="selected.responsable.id" :disabled="busy" @change="assign($event.target.value)" aria-label="Responsable" class="mt-2 w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-1.5 text-sm">
      <option v-for="p in people" :key="p.id" :value="p.id">{{ p.nombre }} ({{ p.rol }})</option>
     </select>
     <h3 class="font-semibold mt-5">Estado</h3>
     <div class="flex flex-wrap gap-2 mt-2"><button v-for="[k,l] in states.filter(s=>s[0]!=='CERRADA')" :key="k" :disabled="busy||selected.estado===k" @click="setState(k)" class="px-3 py-1.5 rounded-lg border text-sm disabled:opacity-40">{{ l }}</button></div>
     <div class="flex gap-2 mt-2"><input v-model="closing" placeholder="Motivo de cierre (obligatorio)" class="flex-1 min-w-0 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-1.5 text-sm"><button :disabled="busy||!closing.trim()" @click="setState('CERRADA')" class="px-3 py-1.5 rounded-lg bg-slate-700 text-white text-sm disabled:opacity-40">Cerrar</button></div>
     <p v-if="selected.motivo_cierre" class="text-xs text-slate-500 mt-1">Cerrada: {{ selected.motivo_cierre }}</p>
     <h3 class="font-semibold mt-5">Qué se puede hacer</h3>
     <p class="text-xs text-slate-500 mt-1">Recomendaciones propuestas, por validar con docentes y Dirección.</p>
     <ul class="mt-2 space-y-2"><li v-for="r in recs?.reglas||[]" :key="r.codigo" class="rounded-lg bg-slate-50 dark:bg-slate-900 p-3 text-sm">
      <p><strong>{{ r.nombre }}</strong></p><p class="mt-1">{{ r.recomendacion }}</p>
      <details class="text-xs text-slate-500 mt-1"><summary class="cursor-pointer">¿Por qué se recomienda?</summary><p class="mt-1">{{ r.dato }} · regla {{ r.codigo }}: {{ r.condicion }}</p></details>
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
      <div class="flex flex-wrap gap-2"><input v-model="form.fecha_planificada" type="date" aria-label="Fecha planificada" class="min-w-0 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-1.5 text-sm"><button :disabled="busy||selected.estado==='CERRADA'" class="flex-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm disabled:opacity-40">Registrar intervención</button></div>
     </form>
     <details class="mt-5"><summary class="cursor-pointer font-semibold">Historial ({{ history.length }})</summary>
     <ol class="mt-2 space-y-2 text-xs"><li v-for="h in history" :key="h.id" class="border-l-2 border-slate-300 dark:border-slate-600 pl-2">
      <p class="text-slate-500">{{ h.registrado_en?.replace('T',' ') }} · {{ h.rol }} · {{ h.tabla==='alertas'?'Alerta':'Intervención' }}</p>
      <p v-for="c in changes(h)" :key="c">{{ c }}</p>
     </li><li v-if="!history.length" class="text-slate-500">Sin cambios registrados.</li></ol></details>
    </template>
   </aside>
  </div>
  <section v-if="tab==='modelo'&&selected&&why" ref="whySection" class="mt-6 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5">
   <div class="flex flex-wrap items-baseline justify-between gap-2">
    <h2 class="text-xl font-semibold">¿Por qué {{ etiquetaCodigo(selected.estudiante) }} tiene alerta?</h2>
    <span class="text-sm text-slate-500">{{ why.curso }} · {{ why.gestion }}<template v-if="why.estudiantes_en_curso"> · comparado con {{ why.estudiantes_en_curso }} estudiantes del curso</template></span>
   </div>
   <div v-if="why.perfil" class="mt-4">
    <p class="text-sm font-semibold mb-2">Situación en cada dimensión <span class="ml-1 px-2 py-0.5 rounded-full text-xs" :class="NIVEL[why.perfil.nivel][1]">{{ NIVEL[why.perfil.nivel][0] }}</span><span v-if="why.perfil.notas_y_asistencia" class="ml-1 px-2 py-0.5 rounded-full border border-red-300 dark:border-red-800 text-xs">Notas y asistencia</span></p>
    <PerfilRiesgo :colores="why.perfil.colores" grande />
   </div>
   <AyudaPantalla class="mt-3" titulo="¿Cómo se lee?"><ul class="space-y-1 list-disc pl-5"><li v-for="l in why.como_leer" :key="l">{{ l }}</li></ul><p v-if="why.perfil">{{ why.perfil.nota }}</p></AyudaPantalla>
   <button @click="showModel=!showModel" :aria-expanded="showModel" class="mt-4 px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-sm">{{ showModel?'Ocultar el análisis del modelo':'Ver el análisis del modelo XGBoost' }}</button>
   <template v-if="showModel">
   <p class="mt-3 text-xs text-slate-500">Corte {{ selected.fecha_corte }} · puntaje {{ score(selected.probabilidad) }} · puesto {{ selected.prioridad.puesto }} de {{ selected.prioridad.de }} en {{ selected.gestion }}. Ranking de prioridad, no riesgo absoluto.</p>
   <div class="grid lg:grid-cols-3 gap-6 mt-4">
    <div class="lg:col-span-1 space-y-4">
     <div class="rounded-lg bg-slate-50 dark:bg-slate-900 p-4">
      <p class="text-sm font-semibold">1. Por qué está en este nivel</p>
      <div class="relative mt-6 h-3 rounded-full opacity-80" :style="gaugeZones(why.nivel.umbral_medio,why.nivel.umbral_alto)" aria-hidden="true">
       <span class="absolute -top-5 text-[10px] text-slate-500 -translate-x-1/2" :style="{left:gaugeLeft(why.nivel.umbral_medio/2)}">bajo</span>
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
      <template v-for="(v,i) in shown" :key="v.variable">
      <tr v-if="v.efecto==='neutro'&&shown[i-1]?.efecto!=='neutro'" class="border-t border-slate-200 dark:border-slate-600"><td colspan="5" class="pt-4 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Consideradas por el modelo, sin efecto en este caso</td></tr>
      <tr class="border-t border-slate-100 dark:border-slate-700">
       <td class="py-2 pr-3">{{ v.etiqueta }}<span class="block text-xs text-slate-400">{{ v.grupo }}</span></td>
       <td class="py-2 pr-3 font-medium">{{ v.valor_texto }}</td>
       <td class="py-2 pr-3 text-slate-500">{{ v.comparacion?.replace('curso: ','')||'—' }}</td>
       <td class="py-2 pr-3"><span v-if="v.efecto==='sube'" class="text-red-700 dark:text-red-300">▲ eleva<span v-if="v.peso_relativo"> ({{ comma(v.peso_relativo,0) }} % de lo que la eleva)</span></span><span v-else-if="v.efecto==='baja'" class="text-emerald-700 dark:text-emerald-300">▼ reduce</span><span v-else class="text-slate-400">{{ v.valor==null&&why.variables.some(x=>x.valor!=null)?'sin dato':'sin efecto' }}</span></td>
       <td class="py-2 pr-3 text-right tabular-nums">{{ v.aporte>0?'+':'' }}{{ comma(v.aporte,3) }}</td>
      </tr>
      </template>
     </tbody>
    </table>
   </div>
   <button @click="showAll=!showAll" class="mt-2 text-sm text-blue-700 dark:text-blue-300 underline">{{ showAll?'Ver solo las 8 principales':`Ver las ${why.variables.length} variables` }}</button>
   <details class="mt-4 text-xs text-slate-500">
    <summary class="cursor-pointer">Cómo se calcula y advertencias</summary>
    <p class="mt-2">{{ why.metodo }} Punto de partida: {{ comma(why.punto_partida,3) }} → puntaje con sus datos: {{ comma(why.puntaje_recalculado,3) }}<span v-if="why.coincide_con_guardado"> (coincide con el puntaje guardado).</span></p>
    <p class="mt-1">{{ why.advertencia }}</p>
   </details>
   </template>
  </section>
 </section>
</template>
