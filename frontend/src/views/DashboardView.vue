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
const cards=computed(()=>{const r=data.value?.resumen;return r?[['Predicciones',r.predicciones,''],['Alertas',r.alertas,''],['Prioridad alta',r.alto,'text-red-600'],
 ['Prioridad media',r.medio,'text-amber-600'],['Interv. pendientes',r.intervenciones_pendientes,''],['Interv. ejecutadas',r.intervenciones_ejecutadas,'text-emerald-600'],['Alertas cerradas',r.alertas_cerradas,'']]:[]})
const stepTotal=computed(()=>Object.values(data.value?.intervenciones||{}).reduce((a,b)=>a+b,0))

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
const byCourse=computed(()=>{const rows=data.value?.alertas_por_curso||[];return {
 labels:rows.map(c=>`${c.curso} · ${c.gestion}`),
 datasets:levels.map(([k,l,c])=>({label:l,data:rows.map(r=>r[k]),backgroundColor:c,...bar}))}})
const byGrade=computed(()=>{const rows=data.value?.promedio_por_grado||[];return {
 labels:rows.map(g=>`${g.grado}.º (n=${g.n})`),
 datasets:(data.value?.bandas||[]).map(b=>({label:b.etiqueta,data:rows.map(g=>g.n?100*g[b.codigo]/g.n:0),counts:rows.map(g=>g[b.codigo]),backgroundColor:bandColors[b.codigo],...bar,borderRadius:0}))}})
const byYear=computed(()=>{const rows=data.value?.evolucion||[];return {
 labels:rows.map(e=>`${e.gestion}`),
 datasets:levels.map(([k,l,c])=>({label:l,data:rows.map(r=>r[k]),backgroundColor:c,...bar}))}})
const bySteps=computed(()=>({labels:steps.map(s=>s[1]),
 datasets:[{label:'Intervenciones',data:steps.map(([k])=>data.value?.intervenciones[k]||0),backgroundColor:steps.map(s=>s[2]),...bar}]}))
const courseOptions=computed(()=>options({horizontal:true}))
const gradeOptions=computed(()=>options({horizontal:true,percent:true,tooltip:{label:c=>`${c.dataset.label}: ${c.dataset.counts[c.dataIndex]} (${c.raw.toFixed(0)} %)`}}))
const yearOptions=computed(()=>options({tooltip:{footer:items=>`de ${data.value.evolucion[items[0].dataIndex].predicciones} predicciones`}}))
const stepOptions=computed(()=>options({horizontal:true,stacked:false,legend:false}))
const courseHeight=computed(()=>`${Math.max(160,26*(data.value?.alertas_por_curso.length||0)+60)}px`)

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
   <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 mt-6">
    <div v-for="[l,v,c] in cards" :key="l" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4">
     <p class="text-xs text-slate-500">{{ l }}</p><p class="text-2xl font-bold mt-1" :class="c">{{ v }}</p>
    </div>
   </div>
   <div class="grid lg:grid-cols-2 gap-6 mt-6">
    <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Alertas por nivel y por curso</h2>
     <div class="mt-3" :style="{height:courseHeight}"><Bar v-if="data.alertas_por_curso.length" :data="byCourse" :options="courseOptions" aria-label="Alertas por nivel y por curso" /></div>
     <p v-if="!data.alertas_por_curso.length" class="text-sm text-slate-500">Sin alertas en esta gestión.</p>
    </article>
    <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Promedio del 1.er trimestre por grado</h2>
     <div class="mt-3 h-72"><Bar :data="byGrade" :options="gradeOptions" aria-label="Distribución del promedio del primer trimestre por grado" /></div>
     <p class="mt-2 text-xs text-slate-500">Escala de valoración de primaria (Ley 070). Cada barra suma 100 % de su grado.</p>
    </article>
    <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Evolución de alertas por gestión</h2>
     <div class="mt-3 h-64"><Bar :data="byYear" :options="yearOptions" aria-label="Alertas por gestión" /></div>
     <p class="mt-2 text-xs text-slate-500">Las gestiones con abandonos conocidos se usaron para entrenar el modelo: sus alertas son retrospectivas.</p>
    </article>
    <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Estado de las intervenciones</h2>
     <div class="mt-3 h-48"><Bar :data="bySteps" :options="stepOptions" aria-label="Estado de las intervenciones" /></div>
     <p v-if="!stepTotal" class="text-sm text-slate-500">Aún no hay intervenciones registradas.</p>
     <p class="mt-2 text-xs text-slate-500">Pendientes = propuesta, aprobada o en curso. Alertas: {{ data.estados_alerta.NUEVA }} nuevas · {{ data.estados_alerta.EN_REVISION }} en revisión · {{ data.estados_alerta.EN_SEGUIMIENTO }} en seguimiento · {{ data.estados_alerta.CERRADA }} cerradas.</p>
    </article>
   </div>
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
