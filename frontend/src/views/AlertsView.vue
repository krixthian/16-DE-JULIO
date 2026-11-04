<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../services/api'
const alerts=ref([]),summary=ref(null),selected=ref(null),items=ref([]),busy=ref(false),error=ref(''),notice=ref('')
const filter=ref({estado:'',gestion:''}),form=ref({recomendacion:'',fecha_planificada:''}),closing=ref('')
const states=[['NUEVA','Nueva'],['EN_REVISION','En revisión'],['EN_SEGUIMIENTO','En seguimiento'],['CERRADA','Cerrada']]
const stepStates=[['PROPUESTA','Propuesta'],['APROBADA','Aprobada'],['EN_CURSO','En curso'],['REALIZADA','Realizada'],['CANCELADA','Cancelada']]
const label=(list,k)=>Object.fromEntries(list)[k]||k
const message=e=>{const d=e.response?.data?.detail;return Array.isArray(d)?d.map(x=>x.msg.replace('Value error, ','')).join(' · '):d||'No se pudo conectar con el servidor.'}
const pct=v=>`${(v*100).toFixed(1)} %`
const years=computed(()=>[...new Set(alerts.value.map(a=>a.gestion))])
const visible=computed(()=>alerts.value.filter(a=>(!filter.value.estado||a.estado===filter.value.estado)&&(!filter.value.gestion||a.gestion===Number(filter.value.gestion))))
const levelClass=n=>n==='ALTO'?'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200':'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'
async function load(){
 busy.value=true;error.value=''
 try{const [a,s]=await Promise.all([api.get('/alertas'),api.get('/alertas/resumen')]);alerts.value=a.data;summary.value=s.data}catch(e){error.value=message(e)}finally{busy.value=false}
}
async function open(a){
 selected.value=a;items.value=[];closing.value='';form.value={recomendacion:'',fecha_planificada:''};notice.value=''
 try{items.value=(await api.get(`/alertas/${a.id}/intervenciones`)).data}catch(e){error.value=message(e)}
}
function replace(a){alerts.value=alerts.value.map(x=>x.id===a.id?a:x);selected.value=a}
async function setState(estado){
 busy.value=true;error.value=''
 try{replace((await api.patch(`/alertas/${selected.value.id}`,{estado,motivo_cierre:estado==='CERRADA'?closing.value.trim():null})).data);notice.value='Estado de la alerta actualizado.'}catch(e){error.value=message(e)}finally{busy.value=false}
}
async function propose(){
 busy.value=true;error.value=''
 try{
  const {data}=await api.post(`/alertas/${selected.value.id}/intervenciones`,{recomendacion:form.value.recomendacion,fecha_planificada:form.value.fecha_planificada||null})
  items.value=[...items.value,data];form.value={recomendacion:'',fecha_planificada:''}
  replace({...selected.value,intervenciones:selected.value.intervenciones+1,estado:selected.value.estado==='NUEVA'?'EN_SEGUIMIENTO':selected.value.estado})
  notice.value='Intervención registrada.'
 }catch(e){error.value=message(e)}finally{busy.value=false}
}
async function advance(i,estado){
 let accion_realizada=null
 if(estado==='REALIZADA'){accion_realizada=window.prompt('Describe la acción realizada:');if(!accion_realizada)return}
 busy.value=true;error.value=''
 try{const {data}=await api.patch(`/intervenciones/${i.id}`,{estado,accion_realizada});items.value=items.value.map(x=>x.id===data.id?data:x)}catch(e){error.value=message(e)}finally{busy.value=false}
}
onMounted(load)
</script>
<template>
 <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Alerta temprana</p>
  <h1 class="text-3xl font-bold">Alertas de riesgo de abandono</h1>
  <p class="mt-2 text-slate-500 dark:text-slate-400 max-w-3xl">Predicción XGBoost al cierre del 1.er trimestre. La probabilidad no está calibrada: úsala para priorizar la revisión, no como diagnóstico.</p>
  <div v-if="error" role="alert" class="mt-6 bg-red-50 text-red-800 rounded-xl p-4">{{ error }}</div>
  <div v-if="notice" class="mt-6 bg-green-50 text-green-800 rounded-xl p-4">{{ notice }}</div>
  <div v-if="summary" class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
   <div class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5"><p class="text-sm text-slate-500">Predicciones</p><p class="text-3xl font-bold mt-2">{{ Object.values(summary.predicciones).reduce((a,b)=>a+b,0) }}</p></div>
   <div class="rounded-xl bg-white dark:bg-slate-800 border border-red-200 dark:border-red-900 p-5"><p class="text-sm text-slate-500">Nivel alto</p><p class="text-3xl font-bold mt-2 text-red-600">{{ summary.predicciones.ALTO||0 }}</p></div>
   <div class="rounded-xl bg-white dark:bg-slate-800 border border-amber-200 dark:border-amber-900 p-5"><p class="text-sm text-slate-500">Nivel medio</p><p class="text-3xl font-bold mt-2 text-amber-600">{{ summary.predicciones.MEDIO||0 }}</p></div>
   <div class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-5"><p class="text-sm text-slate-500">Modelo</p><p class="text-sm font-semibold mt-2 break-all">{{ summary.modelo?.version||'—' }}</p><p class="text-xs text-slate-500 mt-1">Medio ≥ {{ summary.modelo?.umbral_medio }} · Alto ≥ {{ summary.modelo?.umbral_alto }}</p></div>
  </div>
  <div class="flex flex-wrap gap-3 mt-6">
   <select v-model="filter.estado" aria-label="Estado" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todos los estados</option><option v-for="[k,l] in states" :key="k" :value="k">{{ l }}</option></select>
   <select v-model="filter.gestion" aria-label="Gestión" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-800 px-3 py-2"><option value="">Todas las gestiones</option><option v-for="y in years" :key="y" :value="y">{{ y }}</option></select>
  </div>
  <div class="grid lg:grid-cols-5 gap-6 mt-4">
   <div class="lg:col-span-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
    <table class="w-full text-sm">
     <thead class="bg-slate-50 dark:bg-slate-900 text-left"><tr><th class="p-3">Estudiante</th><th class="p-3">Gestión / curso</th><th class="p-3">Riesgo</th><th class="p-3">Estado</th><th class="p-3">Interv.</th></tr></thead>
     <tbody>
      <tr v-if="!visible.length"><td colspan="5" class="p-6 text-center text-slate-500">{{ busy ? 'Cargando…' : 'No hay alertas con estos filtros.' }}</td></tr>
      <tr v-for="a in visible" :key="a.id" @click="open(a)" class="border-t border-slate-100 dark:border-slate-700 cursor-pointer hover:bg-blue-50 dark:hover:bg-slate-700" :class="selected?.id===a.id?'bg-blue-50 dark:bg-slate-700':''">
       <td class="p-3 font-mono">{{ a.estudiante }}</td>
       <td class="p-3">{{ a.gestion }} · {{ a.curso }}<span v-if="a.uso==='RETROSPECTIVO_EN_ENTRENAMIENTO'" class="block text-xs text-slate-500">Retrospectivo (usado en entrenamiento)</span><span v-else class="block text-xs text-blue-600">Cohorte actual</span></td>
       <td class="p-3"><span class="px-2 py-1 rounded-full text-xs font-semibold" :class="levelClass(a.nivel)">{{ a.nivel }}</span> <span class="text-slate-500">{{ pct(a.probabilidad) }}</span></td>
       <td class="p-3">{{ label(states,a.estado) }}</td>
       <td class="p-3 text-center">{{ a.intervenciones }}</td>
      </tr>
     </tbody>
    </table>
   </div>
   <aside class="lg:col-span-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5">
    <p v-if="!selected" class="text-slate-500">Selecciona una alerta para ver sus factores y registrar intervenciones.</p>
    <template v-else>
     <h2 class="font-semibold text-lg">Alerta {{ selected.estudiante }}</h2>
     <p class="text-sm text-slate-500">Corte {{ selected.fecha_corte }} · {{ selected.curso }} · {{ pct(selected.probabilidad) }}</p>
     <h3 class="font-semibold mt-4">Factores que más elevan el riesgo</h3>
     <ul class="mt-2 space-y-1 text-sm"><li v-for="f in selected.factores" :key="f.variable" class="flex justify-between"><span>{{ f.variable }} = {{ typeof f.valor==='number'&&f.valor<1&&f.valor>0 ? f.valor.toFixed(2) : f.valor }}</span><span class="text-slate-500">+{{ f.aporte }}</span></li><li v-if="!selected.factores.length" class="text-slate-500">Sin factores positivos.</li></ul>
     <h3 class="font-semibold mt-5">Estado</h3>
     <div class="flex flex-wrap gap-2 mt-2"><button v-for="[k,l] in states.filter(s=>s[0]!=='CERRADA')" :key="k" :disabled="busy||selected.estado===k" @click="setState(k)" class="px-3 py-1.5 rounded-lg border text-sm disabled:opacity-40">{{ l }}</button></div>
     <div class="flex gap-2 mt-2"><input v-model="closing" placeholder="Motivo de cierre" class="flex-1 rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-1.5 text-sm"><button :disabled="busy||!closing.trim()" @click="setState('CERRADA')" class="px-3 py-1.5 rounded-lg bg-slate-700 text-white text-sm disabled:opacity-40">Cerrar</button></div>
     <p v-if="selected.motivo_cierre" class="text-xs text-slate-500 mt-1">Cerrada: {{ selected.motivo_cierre }}</p>
     <h3 class="font-semibold mt-5">Intervenciones</h3>
     <ul class="mt-2 space-y-3"><li v-for="i in items" :key="i.id" class="rounded-lg border border-slate-200 dark:border-slate-700 p-3 text-sm">
      <p>{{ i.recomendacion }}</p><p class="text-xs text-slate-500 mt-1">{{ label(stepStates,i.estado) }}<span v-if="i.fecha_planificada"> · planificada {{ i.fecha_planificada }}</span></p>
      <p v-if="i.accion_realizada" class="text-xs mt-1">Acción: {{ i.accion_realizada }}</p>
      <div class="flex flex-wrap gap-1 mt-2"><button v-for="[k,l] in stepStates.filter(s=>s[0]!==i.estado&&s[0]!=='PROPUESTA')" :key="k" :disabled="busy" @click="advance(i,k)" class="px-2 py-1 rounded border text-xs">{{ l }}</button></div>
     </li><li v-if="!items.length" class="text-sm text-slate-500">Aún no hay intervenciones.</li></ul>
     <form @submit.prevent="propose" class="mt-4 space-y-2">
      <textarea v-model="form.recomendacion" required minlength="3" rows="2" placeholder="Ej.: citar a la familia, tutoría de nivelación…" class="w-full rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-2 text-sm"></textarea>
      <div class="flex gap-2"><input v-model="form.fecha_planificada" type="date" aria-label="Fecha planificada" class="rounded-lg border border-slate-300 dark:border-slate-600 dark:bg-slate-900 px-3 py-1.5 text-sm"><button :disabled="busy||selected.estado==='CERRADA'" class="flex-1 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm disabled:opacity-40">Registrar intervención</button></div>
     </form>
    </template>
   </aside>
  </div>
 </section>
</template>
