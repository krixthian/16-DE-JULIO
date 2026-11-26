<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Bar, Line } from 'vue-chartjs'
import { Chart as ChartJS, BarElement, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js'
import api from '../services/api'
import AyudaPantalla from '../components/AyudaPantalla.vue'
import PanelPlegable from '../components/PanelPlegable.vue'
ChartJS.register(BarElement, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend)

const data=ref(null),busy=ref(false),error=ref(''),showImportance=ref(false),tab=ref('vigente'),mes=ref('jun')
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
const ea=computed(()=>data.value?.etiqueta_ampliada)
const reg=computed(()=>data.value?.registros)
const alg=computed(()=>data.value?.algoritmos)
const algRows=computed(()=>{const a=alg.value;if(!a)return []
 return ['xgboost','regresion_logistica','random_forest','arbol_decision','regla_promedio_T1','siempre_continuidad'].filter(k=>a.modelos[k]).map(k=>({k,...a.modelos[k],dif:a.diferencia_ap_vs_xgboost[k]}))})
const difText=d=>!d?'—':`${d.media>=0?'+':''}${n(d.media,2)} [${n(d.ic95[0],2)}; ${n(d.ic95[1],2)}] · ${d.ic95[0]>0?'mejor':d.ic95[1]<0?'peor':'no distinguible'}`
const regRows=computed(()=>{const r=reg.value;if(!r)return []
 const c=r.calidad_datos,p=r.patrones_asistencia,racha=Object.entries(p.continuaron_racha_maxima_de_faltas).reduce((a,[k,v])=>Number(k)>a?Number(k):a,0)
 return [
  ['Notas casi iguales en las 9 áreas (desviación < '+n(c.umbral_plano,0)+' puntos)',`${c.notas_planas.abandonaron} de ${c.notas_planas.de_abandonos}`,`${c.notas_planas.continuaron} de ${c.notas_planas.de_continuaron}`],
  ['SER exactamente 3 de 5 en todas las áreas',c.ser_exacto_3_de_5.abandonaron,c.ser_exacto_3_de_5.continuaron],
  ['Autoevaluación exactamente 6,0',c.autoevaluacion_exacta_6.abandonaron,c.autoevaluacion_exacta_6.continuaron],
  ['Última asistencia el último día de clases de un mes',`${p.abandono_desde_fin_de_mes} de ${p.abandonos-p.abandonos_sin_ninguna_asistencia} que asistieron`,'—'],
  ['Racha más larga de faltas seguidas en el año','desde fin de mes hasta noviembre',`${racha} días como máximo`]]})
const pct=f=>`${Math.round(f*100)} %`
const curveChart=computed(()=>{const e=ea.value;if(!e)return null
 return {labels:e.curva_abandono.map(c=>pct(c.fraccion)),datasets:[
  {label:`Abandono (${data.value.modelo.positivos} casos)`,data:e.curva_abandono.map(c=>c.average_precision),borderColor:colors.orange,backgroundColor:colors.orange,borderWidth:2,pointRadius:5},
  {label:`No aprueba el año (${e.etiqueta.positivos} casos)`,data:e.curva_ampliada.map(c=>c.average_precision),borderColor:colors.blue,backgroundColor:colors.blue,borderWidth:2,pointRadius:5,borderDash:[6,4]}]}})
const curveOptions=computed(()=>{const o=base({title:'Average precision (AP)'});o.scales.y.max=1
 o.scales.x.title={display:true,text:'Parte de los casos usados para entrenar',color:dark.value?'#cbd5e1':'#475569'}
 o.plugins.tooltip={callbacks:{footer:items=>{const e=ea.value,i=items[0].dataIndex,c=(items[0].datasetIndex?e.curva_ampliada:e.curva_abandono)[i];return `≈ ${n(c.positivos_entrenamiento,1)} casos en el entrenamiento · AP ${n(c.average_precision)} ± ${n(c.average_precision_std)}`}}};return o})
const rulesChart=computed(()=>{const e=ea.value;if(!e)return null
 return {labels:e.metodos.map(m=>m.nombre),datasets:[
  {label:'Para detectar abandono',data:e.metodos.map(m=>e.ap_abandono[m.modelo]),backgroundColor:colors.orange,...bar},
  {label:'Para detectar "no aprueba el año"',data:e.metodos.map(m=>e.ap_ampliada[m.modelo]),backgroundColor:colors.blue,...bar}]}})
const seg=computed(()=>data.value?.seguimiento)
const mesLargo={feb:'Febrero',mar:'Marzo',abr:'Abril',may:'Mayo',jun:'Junio',jul:'Julio',ago:'Agosto',sep:'Septiembre',oct:'Octubre'}
const segChart=computed(()=>{const s=seg.value;if(!s)return null
 return {labels:s.cortes.map(c=>mesLargo[c.mes]),datasets:[
  {label:'XGBoost con lo registrado hasta fin de mes',data:s.cortes.map(c=>c.average_precision),borderColor:colors.blue,backgroundColor:colors.blue,borderWidth:2,pointRadius:5},
  {label:'Azar',data:s.cortes.map(c=>c.azar),borderColor:colors.gray,backgroundColor:colors.gray,borderWidth:2,pointRadius:0,borderDash:[6,4]}]}})
const segOptions=computed(()=>{const o=base({title:'Average precision (AP)'});o.scales.y.max=1
 o.plugins.tooltip={callbacks:{footer:items=>{const c=seg.value.cortes[items[0].dataIndex];return `Detecta ${n(c.verdaderos_positivos,1)} de ${c.abandonos} · ${n(c.falsos_positivos,1)} falsas alarmas`}}};return o})
// Abre en abril: el corte del objetivo (cierre del 1.er trimestre), no el mes con mejor resultado.
const corte=computed(()=>seg.value?.cortes.find(c=>c.mes===mes.value))
const combinada=computed(()=>seg.value?.alerta_combinada?.[mes.value])
const nivelesAlerta=[['URGENTE','Urgente','text-red-700 dark:text-red-400'],['ROJO','Rojo','text-red-600'],['AMARILLO','Amarillo','text-amber-600'],['VERDE','Verde','text-emerald-600']]
const totalNivel=k=>Object.values(combinada.value[k]).reduce((a,b)=>a+b,0)
const lecturaMes=computed(()=>['feb','mar','abr','may'].includes(mes.value)?'Antes de que dejen de asistir, el modelo no se distingue del azar.'
 :['sep','oct'].includes(mes.value)?'No cuenta como mérito: el abandono se define por no asistir en el 3.er trimestre.'
 :'Detecta a quienes ya dejaron de venir; no lo predice antes.')
const d5=computed(()=>seg.value?.diario?.['5_faltas'])
const curveFirst=computed(()=>ea.value?.curva_abandono?.[0]),curveLast=computed(()=>ea.value?.curva_abandono?.at(-1))

async function load(){
 busy.value=true;error.value=''
 try{data.value=JSON.parse(JSON.stringify((await api.get('/modelo/resultados')).data).replaceAll('XGBoost (modelo en uso)','XGBoost (modelo anterior)'))}catch(e){error.value=message(e)}finally{busy.value=false}
}
onMounted(()=>{observer.observe(document.documentElement,{attributes:true,attributeFilter:['class']});load()})
onBeforeUnmount(()=>observer.disconnect())
</script>
<template>
 <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Alerta temprana</p>
  <h1 class="text-3xl font-bold">Resultados del modelo</h1>
  <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }}</div>
  <p v-if="busy&&!data" class="mt-6 text-slate-500">Cargando…</p>
  <template v-if="data">
   <div class="flex flex-wrap gap-2 mt-6 border-b border-slate-200 dark:border-slate-700" role="tablist">
    <button v-for="[k,l] in [['vigente','Modelo vigente']]" :key="k" role="tab" :aria-selected="tab===k" @click="tab=k" class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab===k?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">{{ l }}</button>
   </div>
   <!-- Seguimiento continuo: modelo vigente -->
   <section v-if="tab==='vigente'&&seg" class="mt-5">
    <div v-if="corte" class="mt-5">
     <div class="flex flex-wrap items-center gap-3"><label for="mesResultados" class="text-sm font-semibold">Resultados al cierre de</label>
      <select id="mesResultados" v-model="mes" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-1.5 text-sm"><option v-for="c in seg.cortes" :key="c.mes" :value="c.mes">{{ mesLargo[c.mes] }}{{ c.mes==='abr'?' (1.er trimestre)':'' }}</option></select></div>
     <article v-if="combinada" class="mt-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5">
      <h2 class="font-semibold">Alerta combinada <span class="font-normal text-sm text-slate-500">· notas, actitud y asistencia</span></h2>
      <div class="grid md:grid-cols-2 gap-5 mt-3">
       <div v-for="[k,l] in [['abandonaron','Abandonaron'],['continuaron','Continuaron']]" :key="k">
        <p class="text-sm text-slate-500">{{ l }} ({{ totalNivel(k) }})</p>
        <div class="grid grid-cols-4 gap-2 mt-2"><div v-for="[v,t,c] in nivelesAlerta" :key="v" class="rounded-lg bg-slate-50 dark:bg-slate-900 p-2 text-center"><p class="text-xl font-bold" :class="c">{{ combinada[k][v] }}</p><p class="text-xs text-slate-500">{{ t }}</p></div></div>
       </div>
      </div>
      <p class="mt-3 text-sm text-slate-500">Las faltas detectan el abandono; las notas y la actitud señalan a quién más apoyar.</p>
     </article>
     <p class="mt-5 text-sm font-semibold">Métricas de XGBoost</p>
     <div class="grid grid-cols-2 lg:grid-cols-5 gap-3 mt-3">
      <div v-for="[l,k,extra] in [['ROC AUC','roc_auc','azar: 0,500'],['Average precision','average_precision',`azar: ${n(corte.azar)}`],['F1','f1',''],['Sensibilidad','sensibilidad',`detecta ${n(corte.verdaderos_positivos,2)} de ${corte.abandonos}`],['Precisión','precision',`${n(corte.falsos_positivos,1)} falsas alarmas`]]" :key="k" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4">
       <p class="text-xs text-slate-500">{{ l }}</p><p class="text-2xl font-bold mt-1">{{ n(corte[k]) }}</p><p class="text-xs text-slate-500">IC 95 % {{ ic(corte,k) }}</p><p v-if="extra" class="text-xs text-slate-500">{{ extra }}</p>
      </div>
     </div>
     <p class="mt-2 text-sm text-slate-500">{{ lecturaMes }}</p>
    </div>
    <p class="mt-5 text-sm font-semibold">XGBoost frente al azar, mes a mes</p>
    <div class="h-72 mt-2"><Line :data="segChart" :options="segOptions" aria-label="Average precision por mes del seguimiento continuo frente al azar" /></div>
    <PanelPlegable class="mt-4" titulo="Cifras de cada mes" resumen="AP, ROC AUC, detectados y falsas alarmas"><div class="overflow-x-auto"><table class="w-full text-sm"><thead class="text-left text-slate-500"><tr><th class="py-2 pr-3">Fin de mes</th><th class="py-2 pr-3 text-right">AP [IC 95 %]</th><th class="py-2 pr-3 text-right">ROC AUC</th><th class="py-2 pr-3 text-right">Detecta (XGBoost)</th><th class="py-2 pr-3 text-right">Falsas alarmas</th><th class="py-2 pr-3 text-right">5 faltas seguidas</th></tr></thead>
     <tbody><tr v-for="c in seg.cortes" :key="c.mes" class="border-t border-slate-100 dark:border-slate-700">
      <td class="py-2 pr-3">{{ mesLargo[c.mes] }}</td><td class="py-2 pr-3 text-right tabular-nums">{{ n(c.average_precision,3) }} <span class="text-xs text-slate-500">[{{ n(c.ic95_ap?.[0],2) }} – {{ n(c.ic95_ap?.[1],2) }}]</span></td>
      <td class="py-2 pr-3 text-right tabular-nums">{{ n(c.roc_auc,2) }}</td><td class="py-2 pr-3 text-right tabular-nums">{{ n(c.verdaderos_positivos,1) }} de {{ c.abandonos }}</td>
      <td class="py-2 pr-3 text-right tabular-nums">{{ n(c.falsos_positivos,1) }}</td><td class="py-2 pr-3 text-right tabular-nums">{{ c.regla_5.detectados }} · {{ c.regla_5.falsas_alarmas }} FA</td></tr></tbody></table></div></PanelPlegable>
   </section>
   <div v-if="tab==='anterior'" class="mt-5 space-y-3">
   <!-- Datos y protocolo -->
   <p class="text-sm text-slate-500">Un solo corte al 30 de abril, con la versión parcial de los registros. <strong>No es el resultado vigente</strong>: con los registros completos no anticipa.</p>
   <!-- Métricas principales -->
   <div v-if="xgb" class="grid grid-cols-2 lg:grid-cols-5 gap-3">
    <div v-for="[l,k,extra] in [['ROC AUC','roc_auc',''],['Average precision','average_precision',''],['F1','f1',''],['Sensibilidad','sensibilidad',`detecta ${n(xgb.verdaderos_positivos,2)} de ${data.modelo.positivos}`],['Precisión','precision',`${n(xgb.falsos_positivos,1)} falsas alarmas`]]" :key="k" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4">
     <p class="text-xs text-slate-500">{{ l }}</p><p class="text-2xl font-bold mt-1">{{ n(xgb[k]) }}</p>
     <p class="text-xs text-slate-500">IC 95 % {{ ic(xgb,k) }}</p><p v-if="extra" class="text-xs text-slate-500">{{ extra }}</p>
    </div>
   </div>
   <PanelPlegable titulo="Datos y método">
    <p><strong>{{ data.modelo.version }}</strong> · {{ data.modelo.algoritmo }} · {{ data.modelo.variables }} variables del 1.er trimestre (sin datos posteriores al corte)</p>
    <p class="mt-1">Datos: <strong>{{ data.modelo.filas }} matrículas</strong> de {{ data.modelo.estudiantes }} estudiantes ({{ data.modelo.gestiones?.join(', ') }}), con <strong>{{ data.modelo.positivos }} abandonos</strong> ({{ data.modelo.estudiantes_positivos }} estudiantes).</p>
    <p class="mt-1 text-slate-500">{{ data.modelo.protocolo }}</p>
    <p class="mt-1 text-slate-500">Las cifras son la media de 20 repeticiones de validación cruzada agrupada por estudiante, con umbral 0,5. Los intervalos son amplios porque solo hay {{ data.modelo.positivos }} abandonos.</p>
   </PanelPlegable>

    <!-- Matriz de confusión -->
    <PanelPlegable v-if="data.matriz_confusion" titulo="Matriz de confusión (media de 20 repeticiones)">
     <div class="grid grid-cols-[auto_1fr_1fr] gap-2 mt-4 text-sm text-center">
      <span></span><span class="text-xs text-slate-500">Predice: abandona</span><span class="text-xs text-slate-500">Predice: continúa</span>
      <span class="text-xs text-slate-500 self-center text-right">Real: abandonó ({{ data.matriz_confusion.positivos }})</span>
      <div class="rounded-lg bg-emerald-100 dark:bg-emerald-900/40 p-4"><p class="text-2xl font-bold">{{ n(data.matriz_confusion.verdaderos_positivos,2) }}</p><p class="text-xs">detectados</p></div>
      <div class="rounded-lg bg-red-100 dark:bg-red-900/40 p-4"><p class="text-2xl font-bold">{{ n(data.matriz_confusion.falsos_negativos,2) }}</p><p class="text-xs">no detectados</p></div>
      <span class="text-xs text-slate-500 self-center text-right">Real: continuó ({{ data.matriz_confusion.negativos }})</span>
      <div class="rounded-lg bg-amber-100 dark:bg-amber-900/40 p-4"><p class="text-2xl font-bold">{{ n(data.matriz_confusion.falsos_positivos,2) }}</p><p class="text-xs">falsas alarmas</p></div>
      <div class="rounded-lg bg-slate-100 dark:bg-slate-700 p-4"><p class="text-2xl font-bold">{{ n(data.matriz_confusion.verdaderos_negativos,1) }}</p><p class="text-xs">correctos sin alerta</p></div>
     </div>
    </PanelPlegable>
    <!-- Comparación con baselines -->
    <PanelPlegable titulo="Comparación con otros métodos">
     <div class="mt-3 h-64"><Bar :data="comparisonChart" :options="base({horizontal:true,max:1})" aria-label="Comparación de AP y F1 entre métodos" /></div>
     <p class="mt-2 text-xs text-slate-500">XGBoost supera ampliamente a las reglas simples. La regresión logística logra resultados iguales o mejores, con intervalos solapados: XGBoost se mantiene porque permite explicar cada alerta.</p>
    </PanelPlegable>
   <PanelPlegable titulo="Tabla completa con intervalos de confianza">
    <div class="overflow-x-auto mt-3"><table class="w-full">
     <thead class="text-left text-slate-500"><tr><th class="py-1 pr-3">Método</th><th class="pr-3">ROC AUC</th><th class="pr-3">AP [IC 95 %]</th><th class="pr-3">Sensibilidad</th><th class="pr-3">Precisión</th><th class="pr-3">F1</th><th>% marcados</th></tr></thead>
     <tbody><tr v-for="c in compared" :key="c.modelo" class="border-t border-slate-100 dark:border-slate-700"><td class="py-1 pr-3">{{ c.nombre }}</td><td class="pr-3">{{ n(c.roc_auc) }} {{ ic(c,'roc_auc') }}</td><td class="pr-3">{{ n(c.average_precision) }} {{ ic(c,'average_precision') }}</td><td class="pr-3">{{ n(c.sensibilidad,2) }}</td><td class="pr-3">{{ n(c.precision,2) }}</td><td class="pr-3">{{ n(c.f1,2) }}</td><td>{{ c.tasa_marcados==null?'—':n(100*c.tasa_marcados,1)+' %' }}</td></tr></tbody>
    </table></div>
   </PanelPlegable>

   <!-- ¿Un algoritmo más sencillo? -->
   <PanelPlegable v-if="alg" titulo="¿Un algoritmo más sencillo rinde igual?">
    <p class="text-sm text-slate-500 mt-1">Mismas 19 variables y misma validación por estudiante (5 pliegues × 20 repeticiones); hiperparámetros fijados antes, sin búsqueda. Diferencia de AP frente a XGBoost con IC 95 % (bootstrap pareado por estudiante).</p>
    <div class="overflow-x-auto mt-3"><table class="w-full text-sm"><thead class="text-left text-slate-500"><tr><th class="py-2 pr-3">Algoritmo</th><th class="py-2 pr-3">AP</th><th class="py-2 pr-3">Detecta (de {{ data.modelo.positivos }})</th><th class="py-2 pr-3">Falsas alarmas</th><th class="py-2">Frente a XGBoost</th></tr></thead>
     <tbody class="divide-y divide-slate-100 dark:divide-slate-700"><tr v-for="r in algRows" :key="r.k" :class="r.k==='xgboost'?'font-semibold':''">
      <td class="py-2 pr-3">{{ r.nombre }}</td><td class="py-2 pr-3">{{ n(r.average_precision) }} <span class="text-xs text-slate-500">{{ ic(r,'average_precision') }}</span></td>
      <td class="py-2 pr-3">{{ r.verdaderos_positivos==null?'—':n(r.verdaderos_positivos,1) }}</td><td class="py-2 pr-3">{{ r.falsos_positivos==null?'—':n(r.falsos_positivos,1) }}</td>
      <td class="py-2" :class="r.dif&&r.dif.ic95[1]<0?'text-red-600':''">{{ r.k==='xgboost'?'referencia':difText(r.dif) }}</td></tr></tbody></table></div>
    <p class="mt-3 text-sm">Un <strong>árbol de decisión</strong> solo es peor de forma distinguible. La <strong>regresión logística</strong> y <strong>Random Forest</strong> rinden igual que XGBoost: XGBoost no es superior, se mantiene por las explicaciones de cada alerta. Con notas registradas de forma estándar para quienes abandonaron, cualquier método que use el promedio separa parecido.</p>
   </PanelPlegable>

   <!-- Dimensiones de riesgo -->
   <PanelPlegable v-if="data.dimensiones" titulo="Variables de riesgo por dimensión">
    <p class="text-sm text-slate-500 mt-1">Las 9 notas por área no son 9 riesgos distintos: forman una dimensión académica. El modelo actual usa {{ data.dimensiones.variables_modelo }} variables, las que existen en los registros históricos 2021-2025. El sistema ya calcula {{ data.dimensiones.variables_sistema }} (versión {{ data.dimensiones.version_sistema }}) desde sus módulos, para reentrenar cuando la escuela acumule registros.</p>
    <div class="grid sm:grid-cols-2 xl:grid-cols-4 gap-4 mt-4">
     <div v-for="d in data.dimensiones.dimensiones" :key="d.clave" class="rounded-lg border border-slate-200 dark:border-slate-700 p-4 flex flex-col">
      <p class="font-semibold">{{ d.nombre }}</p>
      <p class="text-xs text-slate-500 mt-1">{{ d.descripcion }}</p>
      <template v-if="d.porcentaje!=null">
       <p class="text-2xl font-bold mt-3">{{ n(d.porcentaje,1) }} %</p>
       <div class="h-2 rounded bg-slate-100 dark:bg-slate-700 mt-1"><div class="h-2 rounded bg-blue-600" :style="{width:`${Math.min(100,d.porcentaje)}%`}"></div></div>
       <p class="text-xs text-slate-500 mt-1">del peso del modelo actual</p>
      </template>
      <p class="text-sm mt-3 font-medium">Modelo actual ({{ d.modelo.length }})</p>
      <p v-if="d.modelo.length" class="text-xs text-slate-600 dark:text-slate-300 mt-1">{{ d.modelo.join(' · ') }}</p>
      <p v-else class="text-xs text-amber-700 dark:text-amber-300 mt-1">Sin variables: los registros históricos no traen citaciones ni incidentes. El sistema ya los registra.</p>
      <details class="mt-3 text-xs">
       <summary class="cursor-pointer text-blue-700 dark:text-blue-300">El sistema además calcula {{ d.sistema.length }}</summary>
       <ul class="mt-2 space-y-1 list-disc pl-4 text-slate-600 dark:text-slate-300"><li v-for="v in d.sistema" :key="v.variable">{{ v.descripcion }}</li></ul>
      </details>
     </div>
    </div>
   </PanelPlegable>

   <!-- Importancia -->
   <PanelPlegable v-if="data.importancia" titulo="¿En qué se fija el modelo? Importancia de cada variable">
    <p class="text-sm text-slate-500 mt-1">Peso medio de cada variable en las {{ data.importancia.filas }} predicciones (valores SHAP). Colores: <span class="text-[#2a78d6] font-medium">notas por área</span> · <span class="text-[#eb6834] font-medium">rendimiento general</span> · <span class="text-[#1baf7a] font-medium">asistencia</span> · <span class="text-slate-400 font-medium">datos del estudiante</span>.</p>
    <div class="mt-3" :style="{height:showImportance?'520px':'320px'}"><Bar :data="importanceChart" :options="importanceOptions" aria-label="Importancia de cada variable" /></div>
    <button @click="showImportance=!showImportance" class="mt-2 text-sm text-blue-700 dark:text-blue-300 underline">{{ showImportance?'Ver las 10 principales':'Ver las 19 variables' }}</button>
    <p class="mt-2 text-sm">El <strong>{{ data.importancia.variables[0].etiqueta.toLowerCase() }}</strong> concentra el <strong>{{ n(data.importancia.variables[0].porcentaje,1) }} %</strong> del peso: el modelo depende sobre todo de esa variable.</p>
   </PanelPlegable>

    <!-- Umbrales -->
    <PanelPlegable v-if="thresholds.length" titulo="Elección del umbral">
     <div class="mt-3 h-64"><Line :data="thresholdChart" :options="thresholdOptions" aria-label="Detectados y falsas alarmas según el umbral" /></div>
     <p class="mt-2 text-xs text-slate-500">Propuesta: alertar desde {{ n(data.modelo.umbral_medio,1) }} (MEDIO) y priorizar desde {{ n(data.modelo.umbral_alto,1) }} (ALTO), pendiente de validar con Dirección. La tabla es descriptiva: el umbral no se ajustó con los datos de evaluación.</p>
    </PanelPlegable>
    <!-- Ajuste y calibración -->
    <PanelPlegable v-if="data.ajuste" titulo="Ajuste de hiperparámetros y calibración">
     <p class="mt-2">Se probaron <strong>{{ data.ajuste.configuraciones }} configuraciones</strong> con validación anidada y un criterio fijado antes de ver los resultados.</p>
     <ul class="mt-2 space-y-1">
      <li>• AP del ajustado: <strong>{{ n(data.ajuste.ajustado.average_precision) }}</strong> frente a {{ n(xgb?.average_precision) }} del base. Diferencia {{ n(data.ajuste.diferencia?.average_precision?.media) }}, IC 95 % [{{ n(data.ajuste.diferencia?.average_precision?.ic95?.[0]) }}; {{ n(data.ajuste.diferencia?.average_precision?.ic95?.[1]) }}]: incluye el cero.</li>
      <li>• {{ data.ajuste.estabilidad.configuraciones_distintas }} configuraciones distintas elegidas en {{ data.ajuste.estabilidad.pliegues_externos }} pliegues: ninguna domina.</li>
      <li>• Calibración: Brier {{ n(data.ajuste.calibracion.xgboost_base,4) }} sin calibrar frente a {{ n(data.ajuste.calibracion.xgboost_base_sigmoide,4) }} con sigmoide; sin mejora distinguible.</li>
     </ul>
     <p class="mt-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 p-3"><strong>Decisión:</strong> {{ data.ajuste.decision?.conclusion }}</p>
    </PanelPlegable>

    <!-- Balanceo -->
    <PanelPlegable v-if="balance.length" titulo="Desbalance de clases: ¿ayuda SMOTE?">
     <p class="text-sm text-slate-500 mt-1">{{ data.modelo.positivos }} abandonos frente a {{ data.modelo.filas - data.modelo.positivos }} continuidades. El remuestreo se aplicó solo dentro de cada pliegue de entrenamiento.</p>
     <div class="mt-3 h-72"><Bar :data="balanceChart" :options="balanceOptions" aria-label="AP según el método de balanceo" /></div>
     <p class="mt-2 text-xs text-slate-500">Ninguna variante supera a scale_pos_weight, el método en uso. SMOTE baja la AP y aumenta las falsas alarmas; sin balanceo se pierde casi la mitad de los abandonos.</p>
    </PanelPlegable>
    <!-- Temporal y limitaciones -->
    <PanelPlegable titulo="Validación temporal y limitaciones">
     <p v-if="data.temporal" class="mt-2">Entrenando con 2021-2023 ({{ data.temporal.entrenamiento }} matrículas) y evaluando en 2024 ({{ data.temporal.evaluacion }} matrículas, {{ data.temporal.positivos_evaluacion }} abandonos): detecta <strong>{{ data.temporal.xgboost.verdaderos_positivos }} de {{ data.temporal.positivos_evaluacion }}</strong>, con <strong>{{ data.temporal.xgboost.falsos_positivos }} falsas alarmas</strong> (AP {{ n(data.temporal.xgboost.average_precision) }}).</p>
     <p v-if="separation.length" class="mt-2">Matrículas con promedio T1 ≤ 66: <span v-for="([y,v],i) in separation" :key="y">{{ y }}: {{ v.abandono }} abandonaron y {{ v.sin_abandono }} no<span v-if="i<separation.length-1"> · </span></span>. En 2021-2023 la separación es perfecta, y eso infla las métricas.</p>
     <h3 class="font-semibold mt-4">Limitaciones registradas con el modelo</h3>
     <ul class="mt-1 space-y-1 list-disc pl-5 text-slate-600 dark:text-slate-300"><li v-for="l in data.limitaciones" :key="l">{{ l }}</li></ul>
    </PanelPlegable>
   <!-- Archivos recibidos: versión parcial -->
   <PanelPlegable v-if="reg" titulo="Lo que muestran los archivos recibidos (versión parcial)">
    <p class="text-sm text-slate-500 mt-1">Asistencia día por día y notas por actividad (SER, SABER, HACER, DECIDIR) de los archivos recibidos: {{ reg.matriculas }} matrículas emparejadas sin nombres. Análisis pedido por el docente revisor para ir más allá de los totales trimestrales.</p>
    <div class="overflow-x-auto mt-3"><table class="w-full text-sm"><thead class="text-left text-slate-500"><tr><th class="py-2 pr-3">Señal en el registro</th><th class="py-2 pr-3">Abandonaron ({{ reg.abandonos }})</th><th class="py-2">Continuaron ({{ reg.matriculas-reg.abandonos }})</th></tr></thead>
     <tbody class="divide-y divide-slate-100 dark:divide-slate-700"><tr v-for="[s,a,c] in regRows" :key="s"><td class="py-2 pr-3">{{ s }}</td><td class="py-2 pr-3 font-semibold">{{ a }}</td><td class="py-2">{{ c }}</td></tr></tbody></table></div>
    <div class="grid md:grid-cols-2 gap-4 mt-4 text-sm">
     <div class="rounded-lg bg-slate-50 dark:bg-slate-900 p-3"><p class="font-semibold">La asistencia del 1.er trimestre no anticipa el abandono</p>
      <p class="mt-1">Modelo solo con asistencia, incluso día por día: AP {{ n(reg.senal_asistencia_t1.asistencia_dia_a_dia_t1.average_precision) }} frente a {{ n(reg.senal_asistencia_t1.azar.average_precision) }} del azar; detecta {{ n(reg.senal_asistencia_t1.asistencia_dia_a_dia_t1.detectados,1) }} de {{ reg.abandonos }}. Quienes abandonaron asistían con normalidad de febrero a abril.</p></div>
     <div class="rounded-lg bg-amber-50 dark:bg-amber-950/30 p-3"><p class="font-semibold">Conclusión</p>
      <p class="mt-1">Las notas de quienes abandonaron se registraron de forma estándar: el patrón que aprende el modelo (promedio 62-66) es en buena parte un patrón de registro, y eso explica sus métricas altas. No se agregaron variables de "uniformidad" (inflarían el resultado). Con estos archivos no se puede concluir sobre estudiantes reales; cuánto anticipa en la realidad se medirá con los registros que el sistema capture día a día.</p></div>
    </div>
    <p class="mt-3 text-xs text-slate-500">Pendiente: confirmar con la Dirección cómo se completan las notas y la asistencia de un estudiante que deja de asistir. Detalle en docs/HALLAZGO_REGISTROS_PEDAGOGICOS.md.</p>
   </PanelPlegable>

   <!-- Etiqueta ampliada y curva de aprendizaje -->
   <PanelPlegable v-if="ea" titulo="¿Son suficientes los casos? Curva de aprendizaje y etiqueta ampliada">
    <p class="text-sm text-slate-500 mt-1">Se probó ampliar la etiqueta a "no aprueba el año" (abandono o reprobación: {{ ea.etiqueta.positivos }} casos en los archivos, incluye los {{ ea.etiqueta.abandonos_incluidos }} abandonos) y se midió cómo cambia el modelo según cuántos casos tiene para aprender. Misma validación por estudiante, 20 repeticiones.</p>
    <div class="grid lg:grid-cols-2 gap-6 mt-4">
     <div>
      <h3 class="text-sm font-semibold">Con más casos, el modelo de abandono mejora</h3>
      <div class="mt-2 h-64"><Line :data="curveChart" :options="curveOptions" aria-label="Curva de aprendizaje: AP según la parte de los casos usados para entrenar" /></div>
      <p class="mt-2 text-xs text-slate-500">Abandono: de AP {{ n(curveFirst.average_precision) }} con ≈ {{ n(curveFirst.positivos_entrenamiento,1) }} casos a {{ n(curveLast.average_precision) }} con ≈ {{ n(curveLast.positivos_entrenamiento,1) }}, y la curva aún no se aplana: el límite es la cantidad de abandonos registrados, no el algoritmo.</p>
     </div>
     <div>
      <h3 class="text-sm font-semibold">Las reglas simples bastan para la reprobación, no para el abandono</h3>
      <div class="mt-2 h-64"><Bar :data="rulesChart" :options="base({horizontal:true,max:1,title:'Average precision (AP), media de 20 repeticiones'})" aria-label="AP de cada método para abandono y para no aprobar el año" /></div>
      <p class="mt-2 text-xs text-slate-500">Para "no aprueba el año", la regla del promedio T1 alcanza AP {{ n(ea.ap_ampliada.regla_promedio_T1) }}, igual que XGBoost ({{ n(ea.ap_ampliada.xgboost) }}). Para el abandono, la misma regla cae a {{ n(ea.ap_abandono.regla_promedio_T1) }} y XGBoost llega a {{ n(ea.ap_abandono.xgboost) }}: quienes abandonan no tienen notas bajas.</p>
     </div>
    </div>
    <p class="mt-4 text-sm rounded-lg bg-slate-50 dark:bg-slate-900 p-3"><strong>Decisión:</strong> se mantiene el modelo de abandono. La etiqueta ampliada se predice con una regla simple (en 2025 detecta {{ ea.temporal_2025.regla_promedio_T1.verdaderos_positivos }} de {{ ea.temporal_2025.positivos }} con {{ ea.temporal_2025.regla_promedio_T1.falsos_positivos }} falsas alarmas, frente a {{ ea.temporal_2025.xgboost.falsos_positivos }} de XGBoost), y esa necesidad ya la cubre la pestaña "Notas bajas".</p>
   </PanelPlegable>
   </div>
   <AyudaPantalla class="mt-6" titulo="Fuentes de las cifras"><p class="text-xs">Registro del modelo en la base y reportes reproducibles del entrenamiento: <span v-for="(v,k) in data.fuentes" :key="k">{{ v || `${k}: no disponible` }} · </span></p></AyudaPantalla>
  </template>
 </section>
</template>
