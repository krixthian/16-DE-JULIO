<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Bar, Line } from 'vue-chartjs'
import { Chart as ChartJS, BarElement, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js'
import api from '../services/api'
ChartJS.register(BarElement, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend)

const data=ref(null),busy=ref(false),error=ref(''),showImportance=ref(false)
const dark=ref(document.documentElement.classList.contains('dark'))
const observer=new MutationObserver(()=>{dark.value=document.documentElement.classList.contains('dark')})
const message=e=>e.response?.data?.detail||'No se pudo conectar con el servidor.'
const n=(v,d=3)=>v==null?'—':Number(v).toFixed(d).replace('.',',')
const ic=(m,k)=>m?.ic95?.[k]?`[${n(m.ic95[k][0],2)} – ${n(m.ic95[k][1],2)}]`:''
const xgb=computed(()=>data.value?.comparacion.find(c=>c.modelo==='xgboost'))
const order=['xgboost','regresion_logistica','regla_promedio_T1','regla_faltas_T1','regla_n_areas_bajo_51','siempre_continuidad']
const compared=computed(()=>[...(data.value?.comparacion||[])].sort((a,b)=>order.indexOf(a.modelo)-order.indexOf(b.modelo)))
const colors={blue:'#2a78d6',orange:'#eb6834',aqua:'#1baf7a',gray:'#b8b6ae',red:'#d93b3b'}

function base({horizontal=false,legend=true,max=null,title=null}={}){
 const ink=dark.value?'#cbd5e1':'#475569',grid=dark.value?'rgba(148,163,184,.15)':'rgba(100,116,139,.15)'
 const value={grid:{color:grid},border:{display:false},ticks:{color:ink},beginAtZero:true,...(max?{max}:{}),...(title?{title:{display:true,text:title,color:ink}}:{})}
 const cat={grid:{display:false},ticks:{color:ink}}
 return {responsive:true,maintainAspectRatio:false,animation:false,indexAxis:horizontal?'y':'x',
  plugins:{legend:{display:legend,position:'top',align:'start',labels:{color:ink,boxWidth:12,boxHeight:12}}},
  scales:horizontal?{x:value,y:cat}:{x:cat,y:value}}
}
const bar={borderRadius:4,borderSkipped:false,maxBarThickness:26}
const comparisonChart=computed(()=>({labels:compared.value.map(c=>c.nombre),datasets:[
 {label:'Average precision (AP)',data:compared.value.map(c=>c.average_precision),backgroundColor:colors.blue,...bar},
 {label:'F1 al umbral',data:compared.value.map(c=>c.f1),backgroundColor:colors.aqua,...bar}]}))
const importance=computed(()=>(data.value?.importancia?.variables||[]).slice(0,showImportance.value?19:10))
const importanceChart=computed(()=>({labels:importance.value.map(v=>v.etiqueta),datasets:[{label:'% del peso en las decisiones',
 data:importance.value.map(v=>v.porcentaje),backgroundColor:importance.value.map(v=>v.grupo==='Notas por área'?colors.blue:v.grupo==='Rendimiento general'?colors.orange:v.grupo==='Asistencia y puntualidad'?colors.aqua:colors.gray),...bar}]}))
const importanceOptions=computed(()=>({...base({horizontal:true,legend:false,title:'% del peso total (|SHAP| medio)'}),
 plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>`${n(c.raw,1)} % del peso`}}}}))
const thresholds=computed(()=>data.value?.ajuste?.umbrales||[])
const thresholdChart=computed(()=>({labels:thresholds.value.map(t=>n(t.umbral,1)),datasets:[
 {label:'Abandonos detectados (de 11)',data:thresholds.value.map(t=>t.verdaderos_positivos),borderColor:colors.blue,backgroundColor:colors.blue,borderWidth:2,pointRadius:4},
 {label:'Falsas alarmas',data:thresholds.value.map(t=>t.falsos_positivos),borderColor:colors.orange,backgroundColor:colors.orange,borderWidth:2,pointRadius:4}]}))
const thresholdOptions=computed(()=>{const o=base({title:'Cantidad media (20 repeticiones)'});o.scales.x.title={display:true,text:'Umbral del puntaje',color:dark.value?'#cbd5e1':'#475569'};return o})
const balance=computed(()=>data.value?.balanceo?.cv_agrupada_5x||[])
const balanceChart=computed(()=>({labels:balance.value.map(b=>b.nombre),datasets:[
 {label:'Average precision (AP)',data:balance.value.map(b=>b.average_precision_media),backgroundColor:colors.blue,...bar},
 {label:'Sensibilidad (abandonos detectados)',data:balance.value.map(b=>b.sensibilidad_media),backgroundColor:colors.aqua,...bar}]}))
const balanceOptions=computed(()=>{const o=base({horizontal:true,max:1,title:'Media de 20 repeticiones'});
 o.plugins.tooltip={callbacks:{footer:items=>{const b=balance.value[items[0].dataIndex];return `Detecta ${n(b.verdaderos_positivos_media,2)} de ${data.value.modelo.positivos} · ${n(b.falsos_positivos_media,2)} falsas alarmas`}}};return o})
const separation=computed(()=>Object.entries(data.value?.separacion_promedio_le_66||{}))

async function load(){
 busy.value=true;error.value=''
 try{data.value=(await api.get('/modelo/resultados')).data}catch(e){error.value=message(e)}finally{busy.value=false}
}
onMounted(()=>{observer.observe(document.documentElement,{attributes:true,attributeFilter:['class']});load()})
onBeforeUnmount(()=>observer.disconnect())
</script>
<template>
 <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Alerta temprana</p>
  <h1 class="text-3xl font-bold">Resultados del modelo</h1>
  <p class="mt-2 text-slate-500 dark:text-slate-400 max-w-4xl">Cómo se evaluó el algoritmo y qué tan bien funciona. Todas las cifras provienen del registro del modelo en la base y de los reportes reproducibles del entrenamiento.</p>
  <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }}</div>
  <p v-if="busy&&!data" class="mt-6 text-slate-500">Cargando…</p>
  <template v-if="data">
   <!-- Datos y protocolo -->
   <div class="mt-6 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 text-sm">
    <p><strong>{{ data.modelo.version }}</strong> · {{ data.modelo.algoritmo }} · {{ data.modelo.variables }} variables del 1.er trimestre (sin datos posteriores al corte)</p>
    <p class="mt-1">Datos: <strong>{{ data.modelo.filas }} matrículas</strong> de {{ data.modelo.estudiantes }} estudiantes ({{ data.modelo.gestiones?.join(', ') }}), con <strong>{{ data.modelo.positivos }} abandonos</strong> ({{ data.modelo.estudiantes_positivos }} estudiantes).</p>
    <p class="mt-1 text-slate-500">{{ data.modelo.protocolo }}</p>
   </div>
   <!-- Métricas principales -->
   <div v-if="xgb" class="grid grid-cols-2 lg:grid-cols-5 gap-3 mt-4">
    <div v-for="[l,k,extra] in [['ROC AUC','roc_auc',''],['Average precision','average_precision',''],['F1','f1',''],['Sensibilidad','sensibilidad',`detecta ${n(xgb.verdaderos_positivos,2)} de ${data.modelo.positivos}`],['Precisión','precision',`${n(xgb.falsos_positivos,1)} falsas alarmas`]]" :key="k" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4">
     <p class="text-xs text-slate-500">{{ l }}</p><p class="text-2xl font-bold mt-1">{{ n(xgb[k]) }}</p>
     <p class="text-xs text-slate-500">IC 95 % {{ ic(xgb,k) }}</p><p v-if="extra" class="text-xs text-slate-500">{{ extra }}</p>
    </div>
   </div>
   <p class="mt-2 text-xs text-slate-500">Media de 20 repeticiones de validación cruzada agrupada por estudiante, con umbral 0,5. Los intervalos son amplios porque solo hay {{ data.modelo.positivos }} abandonos.</p>

   <div class="grid lg:grid-cols-2 gap-6 mt-6">
    <!-- Matriz de confusión -->
    <article v-if="data.matriz_confusion" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Matriz de confusión (media de 20 repeticiones)</h2>
     <div class="grid grid-cols-[auto_1fr_1fr] gap-2 mt-4 text-sm text-center">
      <span></span><span class="text-xs text-slate-500">Predice: abandona</span><span class="text-xs text-slate-500">Predice: continúa</span>
      <span class="text-xs text-slate-500 self-center text-right">Real: abandonó ({{ data.matriz_confusion.positivos }})</span>
      <div class="rounded-lg bg-emerald-100 dark:bg-emerald-900/40 p-4"><p class="text-2xl font-bold">{{ n(data.matriz_confusion.verdaderos_positivos,2) }}</p><p class="text-xs">detectados</p></div>
      <div class="rounded-lg bg-red-100 dark:bg-red-900/40 p-4"><p class="text-2xl font-bold">{{ n(data.matriz_confusion.falsos_negativos,2) }}</p><p class="text-xs">no detectados</p></div>
      <span class="text-xs text-slate-500 self-center text-right">Real: continuó ({{ data.matriz_confusion.negativos }})</span>
      <div class="rounded-lg bg-amber-100 dark:bg-amber-900/40 p-4"><p class="text-2xl font-bold">{{ n(data.matriz_confusion.falsos_positivos,2) }}</p><p class="text-xs">falsas alarmas</p></div>
      <div class="rounded-lg bg-slate-100 dark:bg-slate-700 p-4"><p class="text-2xl font-bold">{{ n(data.matriz_confusion.verdaderos_negativos,1) }}</p><p class="text-xs">correctos sin alerta</p></div>
     </div>
    </article>
    <!-- Comparación con baselines -->
    <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Comparación con otros métodos</h2>
     <div class="mt-3 h-64"><Bar :data="comparisonChart" :options="base({horizontal:true,max:1})" aria-label="Comparación de AP y F1 entre métodos" /></div>
     <p class="mt-2 text-xs text-slate-500">XGBoost supera ampliamente a las reglas simples. La regresión logística logra resultados iguales o mejores, con intervalos solapados: XGBoost se mantiene porque permite explicar cada alerta.</p>
    </article>
   </div>
   <details class="mt-3 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4 text-sm">
    <summary class="cursor-pointer font-semibold">Tabla completa con intervalos de confianza</summary>
    <div class="overflow-x-auto mt-3"><table class="w-full">
     <thead class="text-left text-slate-500"><tr><th class="py-1 pr-3">Método</th><th class="pr-3">ROC AUC</th><th class="pr-3">AP [IC 95 %]</th><th class="pr-3">Sensibilidad</th><th class="pr-3">Precisión</th><th class="pr-3">F1</th><th>% marcados</th></tr></thead>
     <tbody><tr v-for="c in compared" :key="c.modelo" class="border-t border-slate-100 dark:border-slate-700"><td class="py-1 pr-3">{{ c.nombre }}</td><td class="pr-3">{{ n(c.roc_auc) }} {{ ic(c,'roc_auc') }}</td><td class="pr-3">{{ n(c.average_precision) }} {{ ic(c,'average_precision') }}</td><td class="pr-3">{{ n(c.sensibilidad,2) }}</td><td class="pr-3">{{ n(c.precision,2) }}</td><td class="pr-3">{{ n(c.f1,2) }}</td><td>{{ c.tasa_marcados==null?'—':n(100*c.tasa_marcados,1)+' %' }}</td></tr></tbody>
    </table></div>
   </details>

   <!-- Importancia -->
   <article v-if="data.importancia" class="mt-6 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
    <h2 class="font-semibold">¿En qué se fija el modelo? Importancia de cada variable</h2>
    <p class="text-sm text-slate-500 mt-1">Peso medio de cada variable en las {{ data.importancia.filas }} predicciones (valores SHAP). Colores: <span class="text-[#2a78d6] font-medium">notas por área</span> · <span class="text-[#eb6834] font-medium">rendimiento general</span> · <span class="text-[#1baf7a] font-medium">asistencia</span> · <span class="text-slate-400 font-medium">datos del estudiante</span>.</p>
    <div class="mt-3" :style="{height:showImportance?'520px':'320px'}"><Bar :data="importanceChart" :options="importanceOptions" aria-label="Importancia de cada variable" /></div>
    <button @click="showImportance=!showImportance" class="mt-2 text-sm text-blue-700 dark:text-blue-300 underline">{{ showImportance?'Ver las 10 principales':'Ver las 19 variables' }}</button>
    <p class="mt-2 text-sm">El <strong>{{ data.importancia.variables[0].etiqueta.toLowerCase() }}</strong> concentra el <strong>{{ n(data.importancia.variables[0].porcentaje,1) }} %</strong> del peso: el modelo depende sobre todo de esa variable.</p>
   </article>

   <div class="grid lg:grid-cols-2 gap-6 mt-6">
    <!-- Umbrales -->
    <article v-if="thresholds.length" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Elección del umbral</h2>
     <div class="mt-3 h-64"><Line :data="thresholdChart" :options="thresholdOptions" aria-label="Detectados y falsas alarmas según el umbral" /></div>
     <p class="mt-2 text-xs text-slate-500">Propuesta: alertar desde {{ n(data.modelo.umbral_medio,1) }} (MEDIO) y priorizar desde {{ n(data.modelo.umbral_alto,1) }} (ALTO), pendiente de validar con Dirección. La tabla es descriptiva: el umbral no se ajustó con los datos de evaluación.</p>
    </article>
    <!-- Ajuste y calibración -->
    <article v-if="data.ajuste" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5 text-sm">
     <h2 class="font-semibold">Ajuste de hiperparámetros y calibración</h2>
     <p class="mt-2">Se probaron <strong>{{ data.ajuste.configuraciones }} configuraciones</strong> con validación anidada y un criterio fijado antes de ver los resultados.</p>
     <ul class="mt-2 space-y-1">
      <li>• AP del ajustado: <strong>{{ n(data.ajuste.ajustado.average_precision) }}</strong> frente a {{ n(xgb?.average_precision) }} del base. Diferencia {{ n(data.ajuste.diferencia?.average_precision?.media) }}, IC 95 % [{{ n(data.ajuste.diferencia?.average_precision?.ic95?.[0]) }}; {{ n(data.ajuste.diferencia?.average_precision?.ic95?.[1]) }}]: incluye el cero.</li>
      <li>• {{ data.ajuste.estabilidad.configuraciones_distintas }} configuraciones distintas elegidas en {{ data.ajuste.estabilidad.pliegues_externos }} pliegues: ninguna domina.</li>
      <li>• Calibración: Brier {{ n(data.ajuste.calibracion.xgboost_base,4) }} sin calibrar frente a {{ n(data.ajuste.calibracion.xgboost_base_sigmoide,4) }} con sigmoide; sin mejora distinguible.</li>
     </ul>
     <p class="mt-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 p-3"><strong>Decisión:</strong> {{ data.ajuste.decision?.conclusion }}</p>
    </article>
   </div>

   <div class="grid lg:grid-cols-2 gap-6 mt-6">
    <!-- Balanceo -->
    <article v-if="balance.length" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5">
     <h2 class="font-semibold">Desbalance de clases: ¿ayuda SMOTE?</h2>
     <p class="text-sm text-slate-500 mt-1">{{ data.modelo.positivos }} abandonos frente a {{ data.modelo.filas - data.modelo.positivos }} continuidades. El remuestreo se aplicó solo dentro de cada pliegue de entrenamiento.</p>
     <div class="mt-3 h-72"><Bar :data="balanceChart" :options="balanceOptions" aria-label="AP según el método de balanceo" /></div>
     <p class="mt-2 text-xs text-slate-500">Ninguna variante supera a scale_pos_weight, el método en uso. SMOTE baja la AP y aumenta las falsas alarmas; sin balanceo se pierde casi la mitad de los abandonos.</p>
    </article>
    <!-- Temporal y limitaciones -->
    <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5 text-sm">
     <h2 class="font-semibold">Validación temporal y limitaciones</h2>
     <p v-if="data.temporal" class="mt-2">Entrenando con 2021-2023 ({{ data.temporal.entrenamiento }} matrículas) y evaluando en 2024 ({{ data.temporal.evaluacion }} matrículas, {{ data.temporal.positivos_evaluacion }} abandonos): detecta <strong>{{ data.temporal.xgboost.verdaderos_positivos }} de {{ data.temporal.positivos_evaluacion }}</strong>, con <strong>{{ data.temporal.xgboost.falsos_positivos }} falsas alarmas</strong> (AP {{ n(data.temporal.xgboost.average_precision) }}).</p>
     <p v-if="separation.length" class="mt-2">Matrículas con promedio T1 ≤ 66: <span v-for="([y,v],i) in separation" :key="y">{{ y }}: {{ v.abandono }} abandonaron y {{ v.sin_abandono }} no<span v-if="i<separation.length-1"> · </span></span>. En 2021-2023 la separación es perfecta, y eso infla las métricas.</p>
     <h3 class="font-semibold mt-4">Limitaciones registradas con el modelo</h3>
     <ul class="mt-1 space-y-1 list-disc pl-5 text-slate-600 dark:text-slate-300"><li v-for="l in data.limitaciones" :key="l">{{ l }}</li></ul>
    </article>
   </div>
   <p class="mt-6 text-xs text-slate-500">Fuentes: <span v-for="(v,k) in data.fuentes" :key="k">{{ v || `${k}: no disponible` }} · </span></p>
  </template>
 </section>
</template>
