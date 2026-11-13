<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js'
import api from '../services/api'
ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const data=ref(null),gestion=ref(''),busy=ref(false),error=ref(''),report=ref({curso:''}),downloading=ref('')
const dark=ref(document.documentElement.classList.contains('dark'))
const observer=new MutationObserver(()=>{dark.value=document.documentElement.classList.contains('dark')})
const message=e=>e.response?.data?.detail||'No se pudo conectar con el servidor.'
const levels=[['ALTO','Prioridad alta','#d93b3b'],['MEDIO','Prioridad media','#e8a33d']]
const bandColors={ED:'#eb6834',DA:'#f5b48f',DO:'#9cc3ef',DP:'#2a78d6'}
const steps=[['PENDIENTE','Pendientes','#eb6834'],['EJECUTADA','Ejecutadas','#1baf7a'],['CANCELADA','Canceladas','#b8b6ae']]
const th=k=>{const v=data.value?.umbrales?.[k];return v==null?'—':String(v).replace('.',',')}
const pctText=(a,b)=>b?`${(100*a/b).toFixed(1).replace('.',',')} %`:'0 %'
const scope=computed(()=>gestion.value?`en ${gestion.value}`:'en todas las gestiones')
const cardGroups=computed(()=>{const r=data.value?.resumen;if(!r)return []
 return [
  {titulo:'1. Qué detectó el modelo',items:[
   {l:'Matrículas evaluadas',v:r.predicciones,d:'Estudiantes a los que el modelo calculó un puntaje al cierre del 1.er trimestre.'},
   {l:'Alertas generadas',v:r.alertas,d:`${pctText(r.alertas,r.predicciones)} de las evaluadas: puntaje ≥ ${th('medio')}.`},
   {l:'Prioridad alta',v:r.alto,c:'text-red-600',d:`Puntaje ≥ ${th('alto')}: revisar primero.`},
   {l:'Prioridad media',v:r.medio,c:'text-amber-600',d:`Puntaje entre ${th('medio')} y ${th('alto')}.`}]},
  {titulo:'2. De qué año son las alertas',items:[
   {l:'Retrospectivas',v:r.retrospectivas,d:'Años usados para entrenar el modelo: muestran que el modelo reconoce casos pasados; no requieren acción.'},
   {l:'Cohorte actual',v:r.cohorte_actual,c:'text-blue-600',d:'Estudiantes de la gestión en curso: son las que la escuela debe atender.'}]},
  {titulo:'3. Qué se hizo con ellas',items:[
   {l:'Sin intervención',v:r.sin_intervencion,c:r.sin_intervencion?'text-amber-600':'',d:`${r.sin_intervencion} de ${r.alertas} alertas aún no tienen ninguna acción registrada.`},
   {l:'Intervenciones ejecutadas',v:r.intervenciones_ejecutadas,c:'text-emerald-600',d:`Pendientes: ${r.intervenciones_pendientes}.`},
   {l:'Alertas cerradas',v:r.alertas_cerradas,d:'Cerradas con motivo (por ejemplo, el estudiante asiste con normalidad).'}]}]})
const summaryText=computed(()=>{const r=data.value?.resumen;if(!r)return ''
 const partes=[`${r.alertas===1?'Se generó 1 alerta':`Se generaron ${r.alertas} alertas`} ${scope.value} sobre ${r.predicciones} matrículas evaluadas (${pctText(r.alertas,r.predicciones)}): ${r.alto} de prioridad alta y ${r.medio} de prioridad media.`]
 if(r.retrospectivas)partes.push(`${r.retrospectivas} ${r.retrospectivas===1?'es retrospectiva':'son retrospectivas'} (años usados para entrenar) y ${r.cohorte_actual} ${r.cohorte_actual===1?'corresponde':'corresponden'} a la cohorte actual.`)
 partes.push(`Las alertas están en ${r.cursos_con_alerta} de ${r.cursos} cursos.`)
 partes.push(r.con_intervencion?`${r.con_intervencion} de ${r.alertas} alertas ya tienen al menos una intervención; ${r.alertas_cerradas} se cerraron.`:`Ninguna alerta tiene todavía una intervención registrada.`)
 return partes.join(' ')})
const followSteps=[['NUEVA','Nueva','#64748b'],['EN_REVISION','En revisión','#e8a33d'],['EN_SEGUIMIENTO','En seguimiento','#2a78d6'],['CERRADA','Cerrada','#1baf7a']]
const stepTotal=computed(()=>Object.values(data.value?.intervenciones||{}).reduce((a,b)=>a+b,0))
const gradeNote=computed(()=>{const rows=data.value?.promedio_por_grado||[];if(!rows.length)return ''
 const low=rows.map(g=>({g:g.grado,p:g.n?100*(g.ED+g.DA)/g.n:0})).sort((a,b)=>b.p-a.p)[0]
 return `El ${low.g}.º grado tiene la mayor proporción de estudiantes por debajo de "desarrollo óptimo" (${low.p.toFixed(0)} % en ED o DA).`})

// Opciones comunes: texto en tinta neutra, rejilla tenue, barras finas con esquinas redondeadas.
const bar={borderRadius:4,borderSkipped:false,maxBarThickness:28}
function options({horizontal=false,stacked=true,percent=false,legend=true,tooltip}={}){
 const ink=dark.value?'#cbd5e1':'#475569',grid=dark.value?'rgba(148,163,184,.15)':'rgba(100,116,139,.15)'
 const value={stacked,grid:{color:grid},border:{display:false},ticks:{color:ink,precision:0,...(percent?{callback:v=>`${v} %`}:{})},...(percent?{max:100}:{beginAtZero:true})}
 const category={stacked,grid:{display:false},border:{color:grid},ticks:{color:ink}}
 return {responsive:true,maintainAspectRatio:false,indexAxis:horizontal?'y':'x',animation:false,
  interaction:{mode:'index',axis:horizontal?'y':'x',intersect:false},
  plugins:{legend:{display:legend,position:'top',align:'start',labels:{color:ink,boxWidth:12,boxHeight:12,useBorderRadius:true,borderRadius:2}},
   tooltip:{callbacks:tooltip||{}}},
  scales:horizontal?{x:value,y:category}:{x:category,y:value}}
}
const byGrade=computed(()=>{const rows=data.value?.promedio_por_grado||[];return {
 labels:rows.map(g=>`${g.grado}.º (n=${g.n})`),
 datasets:(data.value?.bandas||[]).map(b=>({label:b.etiqueta,data:rows.map(g=>g.n?100*g[b.codigo]/g.n:0),counts:rows.map(g=>g[b.codigo]),backgroundColor:bandColors[b.codigo],...bar,borderRadius:0}))}})
const byYear=computed(()=>{const rows=data.value?.evolucion||[];return {
 labels:rows.map(e=>[`${e.gestion}`,e.retrospectiva?'retrospectiva':'cohorte actual']),
 datasets:levels.map(([k,l,c])=>({label:l,data:rows.map(r=>r[k]),backgroundColor:c,...bar}))}})
const gradeOptions=computed(()=>options({horizontal:true,percent:true,tooltip:{label:c=>`${c.dataset.label}: ${c.dataset.counts[c.dataIndex]} (${c.raw.toFixed(0)} %)`}}))
const yearOptions=computed(()=>{const o=options({tooltip:{footer:items=>{const e=data.value.evolucion[items[0].dataIndex];return `${e.ALTO+e.MEDIO} alertas de ${e.predicciones} matrículas (${pctText(e.ALTO+e.MEDIO,e.predicciones)})`}}})
 o.scales.y.title={display:true,text:'Número de alertas',color:dark.value?'#cbd5e1':'#475569'};return o})

async function download(format){
 downloading.value=format;error.value=''
 const params={gestion:gestion.value,...(report.value.curso?{curso_id:report.value.curso}:{})}
 try{
  const res=await api.get(`/reportes/alertas.${format}`,{params,responseType:'blob'})
  const name=/filename="([^"]+)"/.exec(res.headers['content-disposition']||'')?.[1]||`reporte_alertas.${format}`
  const url=URL.createObjectURL(res.data),link=document.createElement('a')
  link.href=url;link.download=name;link.click();URL.revokeObjectURL(url)
 }catch(e){error.value=e.response?.status===404?'No hay datos para ese curso o gestión.':'No se pudo generar el reporte.'}finally{downloading.value=''}
}
// Pestaña "Análisis del dataset": desbalance, abandono por gestión y grado, y desglose por materia.
const tab=ref('seguimiento'),ds=ref(null),dsError=ref(''),useMedian=ref(true)
const num=(v,d=1)=>v==null?'—':Number(v).toFixed(d).replace('.',',')
const rate=(a,n)=>n?100*a/n:0
const dsGestion=computed(()=>{const r=ds.value?.por_gestion||[];return {labels:r.map(x=>`${x.valor}`),datasets:[{label:'Tasa de abandono (%)',data:r.map(x=>rate(x.abandonos,x.matriculas)),backgroundColor:'#eb6834',borderRadius:4,maxBarThickness:36}]}})
const dsGrado=computed(()=>{const r=ds.value?.por_grado||[];return {labels:r.map(x=>`${x.valor}.º`),datasets:[{label:'Tasa de abandono (%)',data:r.map(x=>rate(x.abandonos,x.matriculas)),backgroundColor:'#eb6834',borderRadius:4,maxBarThickness:36}]}})
const countTooltip=rows=>({callbacks:{label:c=>`${num(c.raw)} % · ${rows()[c.dataIndex].abandonos} de ${rows()[c.dataIndex].matriculas} matrículas`}})
const dsRateOptions=rows=>computed(()=>{const o=options({stacked:false,legend:false});o.plugins.tooltip=countTooltip(rows);o.scales.y.ticks.callback=v=>`${v} %`;o.scales.y.ticks.precision=undefined;return o})
const gestionOptions=dsRateOptions(()=>ds.value?.por_gestion||[]),gradoOptions=dsRateOptions(()=>ds.value?.por_grado||[])
const subjects=computed(()=>ds.value?.materias||[])
const dsMaterias=computed(()=>{const k=useMedian.value?'mediana':'media';return {labels:subjects.value.map(x=>x.materia),datasets:[
 {label:`Nota de los ${ds.value?.resumen.abandonos} que abandonaron`,data:subjects.value.map(x=>x[`${k}_abandonaron`]),backgroundColor:'#d93b3b',borderRadius:4,maxBarThickness:14},
 {label:`Nota de los ${ds.value?.resumen.continuaron} que continuaron`,data:subjects.value.map(x=>x[`${k}_continuaron`]),backgroundColor:'#2a78d6',borderRadius:4,maxBarThickness:14}]}})
const materiasOptions=computed(()=>{const o=options({horizontal:true,stacked:false});o.scales.x.max=100;o.scales.x.title={display:true,text:`Nota ${useMedian.value?'mediana':'media'} del 1.er trimestre, en puntos de 0 a 100 (aprobación desde 51)`,color:dark.value?'#cbd5e1':'#475569'}
 o.plugins.tooltip={callbacks:{label:c=>`${c.datasetIndex===0?'Abandonaron':'Continuaron'}: nota ${useMedian.value?'mediana':'media'} ${num(c.raw)} puntos`}};return o})
const histogram=computed(()=>ds.value?.histograma_promedio||[])
const dsHist=computed(()=>({labels:histogram.value.map(h=>h.rango),datasets:[{label:'Tasa de abandono (%)',data:histogram.value.map(h=>rate(h.abandonaron,h.abandonaron+h.continuaron)),backgroundColor:'#eb6834',borderRadius:4,maxBarThickness:36}]}))
const histOptions=computed(()=>{const o=options({stacked:false,legend:false});o.scales.y.max=100;o.scales.y.ticks.callback=v=>`${v} %`;o.scales.y.ticks.precision=undefined
 o.scales.x.title={display:true,text:'Promedio del 1.er trimestre',color:dark.value?'#cbd5e1':'#475569'}
 o.plugins.tooltip={callbacks:{label:c=>{const h=histogram.value[c.dataIndex];return `${num(c.raw)} % · ${h.abandonaron} de ${h.abandonaron+h.continuaron} matrículas abandonaron`}}};return o})
const areaDiffs=computed(()=>subjects.value.filter(x=>x.codigo!=='promedio').map(x=>x.diferencia))
const bandCell=(m,b)=>{const x=m.bandas.find(y=>y.banda===b);return x?.matriculas?`${x.abandonos} de ${x.matriculas}`:'—'}
async function loadDataset(){
 if(ds.value)return
 dsError.value=''
 try{ds.value=(await api.get('/dashboard/dataset')).data}catch(e){dsError.value=message(e)}
}
function openTab(t){tab.value=t;if(t==='dataset')loadDataset()}
async function load(){
 busy.value=true;error.value=''
 try{data.value=(await api.get('/dashboard',{params:gestion.value?{gestion:gestion.value}:{}})).data}catch(e){error.value=message(e)}finally{busy.value=false}
}
onMounted(()=>{observer.observe(document.documentElement,{attributes:true,attributeFilter:['class']});load()})
onBeforeUnmount(()=>observer.disconnect())
</script>
<template>
 <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Alerta temprana</p>
  <div class="flex flex-wrap items-end justify-between gap-4">
   <div><h1 class="text-3xl font-bold">Panel analítico</h1>
    <p class="mt-2 text-slate-500 dark:text-slate-400 max-w-3xl">Datos de la base (modelo vigente, corte del 1.er trimestre). El modelo apoya, no sustituye, el criterio docente.</p></div>
   <select v-if="tab==='seguimiento'" v-model="gestion" @change="report.curso='';load()" aria-label="Gestión" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2">
    <option value="">Todas las gestiones</option><option v-for="y in data?.gestiones||[]" :key="y" :value="y">{{ y }}</option>
   </select>
  </div>
  <div class="flex flex-wrap gap-2 mt-6 border-b border-slate-200 dark:border-slate-700" role="tablist">
   <button role="tab" :aria-selected="tab==='seguimiento'" @click="openTab('seguimiento')" class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab==='seguimiento'?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">Seguimiento de alertas</button>
   <button role="tab" :aria-selected="tab==='dataset'" @click="openTab('dataset')" class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab==='dataset'?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">Análisis del dataset y por materia</button>
  </div>
  <p v-if="data&&tab==='seguimiento'" class="mt-3 text-xs text-slate-500 max-w-4xl">{{ data.nota }}</p>
  <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }}</div>
  <p v-if="busy&&!data" class="mt-6 text-slate-500">Cargando…</p>
  <section v-if="tab==='dataset'" class="mt-4">
   <div v-if="dsError" role="alert" class="bg-red-50 text-red-800 rounded-xl p-4">{{ dsError }}</div>
   <p v-else-if="!ds" class="text-slate-500">Cargando…</p>
   <template v-else>
    <p class="text-xs text-slate-500 max-w-4xl">{{ ds.nota }} Fuente: {{ ds.fuente }}</p>
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
     <div class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4"><p class="text-xs text-slate-500">Matrículas reales</p><p class="text-2xl font-bold mt-1">{{ ds.resumen.matriculas }}</p></div>
     <div class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4"><p class="text-xs text-slate-500">Abandonaron</p><p class="text-2xl font-bold mt-1 text-red-600">{{ ds.resumen.abandonos }}</p></div>
     <div class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4"><p class="text-xs text-slate-500">Continuaron</p><p class="text-2xl font-bold mt-1">{{ ds.resumen.continuaron }}</p></div>
     <div class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4"><p class="text-xs text-slate-500">Tasa de abandono</p><p class="text-2xl font-bold mt-1">{{ num(100*ds.resumen.tasa_abandono) }} %</p><p class="text-xs text-slate-500">{{ ds.resumen.proporcion }}: clases muy desbalanceadas</p></div>
    </div>
    <div class="grid lg:grid-cols-2 gap-6 mt-6">
     <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
      <h2 class="font-semibold">Abandono por gestión</h2>
      <div class="mt-3 h-56"><Bar :data="dsGestion" :options="gestionOptions" aria-label="Tasa de abandono por gestión" /></div>
      <p class="mt-2 text-xs text-slate-500"><span v-for="(g,i) in ds.por_gestion" :key="g.valor">{{ g.valor }}: {{ g.abandonos }} de {{ g.matriculas }}<span v-if="i<ds.por_gestion.length-1"> · </span></span>. 2021-2023 provienen de pocos cursos históricos.</p>
     </article>
     <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
      <h2 class="font-semibold">Abandono por grado</h2>
      <div class="mt-3 h-56"><Bar :data="dsGrado" :options="gradoOptions" aria-label="Tasa de abandono por grado" /></div>
      <p class="mt-2 text-xs text-slate-500"><span v-for="(g,i) in ds.por_grado" :key="g.valor">{{ g.valor }}.º: {{ g.abandonos }} de {{ g.matriculas }}<span v-if="i<ds.por_grado.length-1"> · </span></span></p>
     </article>
    </div>
    <article class="mt-6 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <div class="flex flex-wrap items-center justify-between gap-3">
      <div><h2 class="font-semibold">Desglose por materia: notas del 1.er trimestre de quienes abandonaron y quienes continuaron</h2>
       <p class="text-xs text-slate-500 mt-1">Cada barra es una <strong>nota (0 a 100)</strong>, no una cantidad de estudiantes. Los grupos son siempre los mismos: {{ ds.resumen.abandonos }} que abandonaron y {{ ds.resumen.continuaron }} que continuaron.</p></div>
      <label class="text-sm flex items-center gap-2"><input type="checkbox" v-model="useMedian"> Usar mediana (no la afectan los casos extremos)</label>
     </div>
     <div class="mt-3 h-96"><Bar :data="dsMaterias" :options="materiasOptions" aria-label="Nota por materia según abandono" /></div>
     <p v-if="areaDiffs.length" class="mt-3 text-sm rounded-lg bg-slate-50 dark:bg-slate-900 p-3">En todas las materias, quienes abandonaron tenían notas más bajas, con una diferencia de medias parecida en todas (entre {{ num(Math.min(...areaDiffs.map(Math.abs))) }} y {{ num(Math.max(...areaDiffs.map(Math.abs))) }} puntos). <strong>Ninguna materia explica por sí sola el abandono</strong>: el patrón es un rendimiento algo más bajo en general, casi siempre por encima de 51.</p>
     <h3 class="font-semibold mt-5 text-sm">Abandonos por banda de valoración (Ley 070) en cada materia</h3>
     <div class="overflow-x-auto mt-2"><table class="w-full text-sm">
      <thead class="text-left text-slate-500"><tr><th class="py-1 pr-3">Materia</th><th class="pr-3">Nota media: abandonaron</th><th class="pr-3">Nota media: continuaron</th><th class="pr-3">Diferencia (puntos)</th><th v-for="b in ds.bandas" :key="b.codigo" class="pr-3" :title="b.etiqueta">{{ b.codigo }}</th></tr></thead>
      <tbody><tr v-for="mt in subjects" :key="mt.codigo" class="border-t border-slate-100 dark:border-slate-700" :class="mt.codigo==='promedio'?'font-semibold':''">
       <td class="py-1 pr-3">{{ mt.materia }}</td><td class="pr-3">{{ num(mt.media_abandonaron) }}</td><td class="pr-3">{{ num(mt.media_continuaron) }}</td><td class="pr-3 text-red-700 dark:text-red-300">{{ num(mt.diferencia) }}</td>
       <td v-for="b in ds.bandas" :key="b.codigo" class="pr-3 text-slate-600 dark:text-slate-300">{{ bandCell(mt,b.codigo) }}</td>
      </tr></tbody>
     </table></div>
     <p class="mt-2 text-xs text-slate-500">Columnas ED a DP: cuántos abandonaron de cuántos estudiantes tenían esa banda en la materia (ej.: «10 de 236» = de 236 con nota entre 51 y 68, abandonaron 10). ED ≤ 50 · DA 51-68 · DO 69-84 · DP 85-100. Los abandonos se concentran en la banda DA (aprobado, pero bajo), no en la reprobada.</p>
    </article>
    <div class="grid lg:grid-cols-2 gap-6 mt-6">
     <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
      <h2 class="font-semibold">Tasa de abandono según el promedio del 1.er trimestre</h2>
      <div class="mt-3 h-64"><Bar :data="dsHist" :options="histOptions" aria-label="Tasa de abandono por rango de promedio" /></div>
      <p class="mt-2 text-xs text-slate-500"><span v-for="(h,i) in histogram" :key="h.rango">{{ h.rango }}: {{ h.abandonaron }}/{{ h.abandonaron+h.continuaron }}<span v-if="i<histogram.length-1"> · </span></span></p>
     </article>
     <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5 text-sm">
      <h2 class="font-semibold">Asistencia y puntualidad en el 1.er trimestre</h2>
      <table class="w-full mt-3"><thead class="text-left text-slate-500"><tr><th class="py-1">Variable</th><th>Abandonaron (mediana · media)</th><th>Continuaron (mediana · media)</th></tr></thead>
       <tbody><tr v-for="a in ds.asistencia" :key="a.variable" class="border-t border-slate-100 dark:border-slate-700">
        <td class="py-1">{{ a.etiqueta }}</td>
        <td>{{ a.variable==='tasa_asistencia_T1'?`${num(100*a.mediana_abandonaron,0)} % · ${num(100*a.abandonaron,0)} %`:`${num(a.mediana_abandonaron)} · ${num(a.abandonaron)}` }}</td>
        <td>{{ a.variable==='tasa_asistencia_T1'?`${num(100*a.mediana_continuaron,0)} % · ${num(100*a.continuaron,0)} %`:`${num(a.mediana_continuaron)} · ${num(a.continuaron)}` }}</td>
       </tr></tbody></table>
      <p class="mt-3 text-xs text-slate-500">La media de faltas de quienes abandonaron sube por un solo caso que no asistió en todo el trimestre; la mediana muestra que la asistencia en el 1.er trimestre fue parecida en ambos grupos.</p>
     </article>
    </div>
   </template>
  </section>
  <template v-if="data&&tab==='seguimiento'">
   <div class="mt-4 rounded-xl border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40 p-4 text-sm text-blue-900 dark:text-blue-100">
    <p class="font-semibold">Resumen {{ scope }}</p>
    <p class="mt-1">{{ summaryText }}</p>
   </div>
   <div class="grid lg:grid-cols-2 gap-4 mt-4">
    <div v-for="g in cardGroups" :key="g.titulo" class="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4" :class="g.items.length>3?'lg:col-span-2':''">
     <p class="text-sm font-semibold">{{ g.titulo }}</p>
     <div class="grid gap-3 mt-3" :class="g.items.length>3?'grid-cols-2 lg:grid-cols-4':g.items.length===3?'grid-cols-1 sm:grid-cols-3':'grid-cols-2'">
      <div v-for="i in g.items" :key="i.l" class="rounded-lg bg-slate-50 dark:bg-slate-900 p-3">
       <p class="text-xs text-slate-500">{{ i.l }}</p><p class="text-2xl font-bold" :class="i.c">{{ i.v }}</p><p class="text-xs text-slate-500 mt-1">{{ i.d }}</p>
      </div>
     </div>
    </div>
   </div>
   <div class="grid lg:grid-cols-2 gap-6 mt-6">
    <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Alertas por gestión</h2>
     <p class="text-xs text-slate-500 mt-1">Cuántas alertas hubo cada año y de qué prioridad. Pasa el mouse sobre una barra para ver de cuántas matrículas.</p>
     <div class="mt-3 h-64"><Bar :data="byYear" :options="yearOptions" aria-label="Alertas por gestión" /></div>
     <table class="w-full text-xs mt-3"><thead class="text-left text-slate-500"><tr><th>Gestión</th><th>Matrículas</th><th>Alertas</th><th>% del año</th><th>Tipo</th></tr></thead>
      <tbody><tr v-for="e in data.evolucion" :key="e.gestion" class="border-t border-slate-100 dark:border-slate-700"><td class="py-1">{{ e.gestion }}</td><td>{{ e.predicciones }}</td><td>{{ e.ALTO+e.MEDIO }} <span class="text-slate-500">({{ e.ALTO }} alta · {{ e.MEDIO }} media)</span></td><td>{{ pctText(e.ALTO+e.MEDIO,e.predicciones) }}</td><td>{{ e.retrospectiva?'Retrospectiva':'Cohorte actual' }}</td></tr></tbody></table>
    </article>
    <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Seguimiento de las alertas</h2>
     <p class="text-xs text-slate-500 mt-1">En qué estado está cada alerta y si ya tiene acciones registradas.</p>
     <div class="mt-4 flex h-8 rounded-lg overflow-hidden" role="img" :aria-label="`Estados de ${data.resumen.alertas} alertas`">
      <div v-for="[k,l,c] in followSteps" v-show="data.estados_alerta[k]" :key="k" :style="{width:`${100*data.estados_alerta[k]/Math.max(1,data.resumen.alertas)}%`,background:c}" class="flex items-center justify-center text-xs font-semibold text-white" :title="`${l}: ${data.estados_alerta[k]}`">{{ data.estados_alerta[k] }}</div>
     </div>
     <div class="flex flex-wrap gap-3 mt-2 text-xs text-slate-600 dark:text-slate-300"><span v-for="[k,l,c] in followSteps" :key="k" class="flex items-center gap-1"><i class="w-3 h-3 rounded-sm inline-block" :style="{background:c}"></i>{{ l }}: {{ data.estados_alerta[k] }}</span></div>
     <div class="grid grid-cols-3 gap-3 mt-5 text-center">
      <div v-for="[k,l,c] in steps" :key="k" class="rounded-lg bg-slate-50 dark:bg-slate-900 p-3"><p class="text-2xl font-bold" :style="{color:data.intervenciones[k]?c:undefined}">{{ data.intervenciones[k] }}</p><p class="text-xs text-slate-500">Intervenciones {{ l.toLowerCase() }}</p></div>
     </div>
     <p v-if="!stepTotal" class="mt-4 rounded-lg bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-100 p-3 text-sm">Todavía no se registró ninguna intervención. Se registran desde <strong>Alertas de riesgo</strong>, al abrir una alerta y adoptar una recomendación (RP01 a RP05).</p>
     <p class="mt-3 text-xs text-slate-500">Pendientes = propuesta, aprobada o en curso. Ejecutadas = realizada con fecha y resultado.</p>
    </article>
   </div>
   <article class="mt-6 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
    <h2 class="font-semibold">Cursos con alertas</h2>
    <p class="text-xs text-slate-500 mt-1">{{ data.resumen.cursos_con_alerta }} de {{ data.resumen.cursos }} cursos tienen al menos una alerta {{ scope }}. El porcentaje indica qué parte del curso está alertada.</p>
    <div v-if="data.alertas_por_curso.length" class="overflow-x-auto mt-3"><table class="w-full text-sm">
     <thead class="text-left text-slate-500"><tr><th class="py-1 pr-3">Curso</th><th class="pr-3">Gestión</th><th class="pr-3">Estudiantes evaluados</th><th class="pr-3">Prioridad alta</th><th class="pr-3">Prioridad media</th><th class="pr-3">% del curso alertado</th></tr></thead>
     <tbody><tr v-for="c in data.alertas_por_curso" :key="c.gestion+c.curso" class="border-t border-slate-100 dark:border-slate-700">
      <td class="py-1 pr-3 font-medium">{{ c.curso }}</td><td class="pr-3">{{ c.gestion }}</td><td class="pr-3">{{ c.matriculas }}</td>
      <td class="pr-3"><span v-if="c.ALTO" class="text-red-600 font-semibold">{{ c.ALTO }}</span><span v-else class="text-slate-400">0</span></td>
      <td class="pr-3"><span v-if="c.MEDIO" class="text-amber-600 font-semibold">{{ c.MEDIO }}</span><span v-else class="text-slate-400">0</span></td>
      <td class="pr-3"><div class="flex items-center gap-2"><div class="h-2 w-24 rounded bg-slate-100 dark:bg-slate-700"><div class="h-2 rounded bg-[#eb6834]" :style="{width:`${Math.min(100,100*(c.ALTO+c.MEDIO)/Math.max(1,c.matriculas)*5)}%`}"></div></div>{{ pctText(c.ALTO+c.MEDIO,c.matriculas) }}</div></td>
     </tr></tbody></table></div>
    <p v-else class="mt-3 text-sm text-slate-500">Sin alertas {{ scope }}.</p>
   </article>
   <article class="mt-6 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
    <h2 class="font-semibold">Rendimiento del 1.er trimestre por grado</h2>
    <p class="text-xs text-slate-500 mt-1">Qué parte de cada grado está en cada banda de la escala de valoración (Ley 070), según el promedio del 1.er trimestre. Cada barra suma el 100 % del grado.</p>
    <div class="mt-3 h-72"><Bar :data="byGrade" :options="gradeOptions" aria-label="Distribución del promedio del primer trimestre por grado" /></div>
    <p class="mt-2 text-sm">{{ gradeNote }}</p>
   </article>
   <article class="mt-6 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
    <h2 class="font-semibold">Reporte de alertas</h2>
    <p class="text-sm text-slate-500 mt-1">PDF imprimible o CSV con alertas, factores e intervenciones. Estudiantes anonimizados; incluye la fecha, el nivel como ranking de prioridad y la nota de que el modelo apoya, no sustituye, el criterio docente.</p>
    <p v-if="!gestion" class="mt-3 text-sm text-amber-700 dark:text-amber-300">Elige una gestión arriba para generar el reporte.</p>
    <div v-else class="flex flex-wrap items-center gap-3 mt-3">
     <select v-model="report.curso" aria-label="Curso del reporte" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-2 text-sm">
      <option value="">Todos los cursos de {{ gestion }}</option><option v-for="c in data.cursos" :key="c.id" :value="c.id">{{ c.curso }}</option>
     </select>
     <button :disabled="!!downloading" @click="download('pdf')" class="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm disabled:opacity-50">{{ downloading==='pdf'?'Generando…':'Descargar PDF' }}</button>
     <button :disabled="!!downloading" @click="download('csv')" class="px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-sm disabled:opacity-50">{{ downloading==='csv'?'Generando…':'Descargar CSV' }}</button>
    </div>
   </article>
   <details class="mt-6 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5 text-sm">
    <summary class="cursor-pointer font-semibold">Ver los datos en tablas</summary>
    <div class="grid md:grid-cols-2 gap-6 mt-4">
     <table class="w-full"><caption class="text-left font-medium mb-1">Alertas por curso</caption><thead class="text-left text-slate-500"><tr><th>Curso</th><th>Gestión</th><th>Alta</th><th>Media</th></tr></thead>
      <tbody><tr v-for="c in data.alertas_por_curso" :key="c.gestion+c.curso"><td>{{ c.curso }}</td><td>{{ c.gestion }}</td><td>{{ c.ALTO }}</td><td>{{ c.MEDIO }}</td></tr></tbody></table>
     <table class="w-full"><caption class="text-left font-medium mb-1">Promedio T1 por grado</caption><thead class="text-left text-slate-500"><tr><th>Grado</th><th>n</th><th v-for="b in data.bandas" :key="b.codigo">{{ b.codigo }}</th></tr></thead>
      <tbody><tr v-for="g in data.promedio_por_grado" :key="g.grado"><td>{{ g.grado }}.º</td><td>{{ g.n }}</td><td v-for="b in data.bandas" :key="b.codigo">{{ g[b.codigo] }}</td></tr></tbody></table>
     <table class="w-full"><caption class="text-left font-medium mb-1">Alertas por gestión</caption><thead class="text-left text-slate-500"><tr><th>Gestión</th><th>Predicciones</th><th>Alta</th><th>Media</th></tr></thead>
      <tbody><tr v-for="e in data.evolucion" :key="e.gestion"><td>{{ e.gestion }}</td><td>{{ e.predicciones }}</td><td>{{ e.ALTO }}</td><td>{{ e.MEDIO }}</td></tr></tbody></table>
     <table class="w-full"><caption class="text-left font-medium mb-1">Intervenciones</caption><tbody><tr v-for="[k,l] in steps" :key="k"><td>{{ l }}</td><td>{{ data.intervenciones[k] }}</td></tr></tbody></table>
    </div>
   </details>
  </template>
 </section>
</template>
