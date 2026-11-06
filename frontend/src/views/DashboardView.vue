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
   <select v-model="gestion" @change="report.curso='';load()" aria-label="Gestión" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2">
    <option value="">Todas las gestiones</option><option v-for="y in data?.gestiones||[]" :key="y" :value="y">{{ y }}</option>
   </select>
  </div>
  <p v-if="data" class="mt-3 text-xs text-slate-500 max-w-4xl">{{ data.nota }}</p>
  <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }}</div>
  <p v-if="busy&&!data" class="mt-6 text-slate-500">Cargando…</p>
  <template v-if="data">
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
