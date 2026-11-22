<script setup>
import { nombreEstudiante } from '../utils/estudiante'
import { computed, onMounted, ref, watch } from 'vue'
import api from '../services/api'
import { useUserStore } from '../stores/user'

const store=useUserStore()
const docente=computed(()=>store.user?.rol==='Docente')
const today=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}
const statuses=[['PRESENTE','Presente'],['FALTA','Falta'],['ATRASO','Atraso'],['LICENCIA','Licencia']]
const tab=ref('registro'),courses=ref([]),course=ref(''),day=ref(today()),sheet=ref(null),hour=ref(1),subject=ref(''),dictada=ref(true)
const rows=ref([]),reason=ref(''),error=ref(''),notice=ref(''),busy=ref(false),saving=ref(false)
const student=ref(''),detail=ref(null),guardians=ref([]),summon=ref({origen:'DOCENTE_MATERIA',materia_id:'',apoderado_id:'',fecha_programada:'',motivo:''})
const message=e=>{const d=e.response?.data?.detail;return Array.isArray(d)?d.map(x=>x.msg.replace('Value error, ','')).join(' · '):d||'No se pudo conectar con el servidor. Intenta nuevamente.'}
const pct=v=>v==null?'—':`${Math.round(v*100)} %`
const session=computed(()=>sheet.value?.sesiones.find(s=>s.periodo===Number(hour.value)))
const existing=computed(()=>!!session.value)
const origins=computed(()=>docente.value?[['DOCENTE_MATERIA','Docente por su materia']]:[['DOCENTE_MATERIA','Docente por su materia'],['DIRECCION','Dirección'],['ORIENTACION','Orientación']])

async function loadCourses(){
 busy.value=true;error.value=''
 try{courses.value=(await api.get('/asistencia/cursos')).data;if(!course.value)course.value=courses.value[0]?.id||''}
 catch(e){error.value=message(e)}finally{busy.value=false}
}
function fillRows(){
 const s=session.value
 if(s){subject.value=s.materia_id;dictada.value=s.dictada}
 rows.value=(sheet.value?.estudiantes||[]).map(x=>{const r=s?.registros?.[String(x.matricula_id)];return {...x,estado:r?.estado||'PRESENTE',justificada:r?.justificada??null,observacion:r?.observacion||''}})
 reason.value=''
}
async function load(){
 if(!course.value||!day.value)return
 busy.value=true;error.value='';notice.value='';sheet.value=null
 try{sheet.value=(await api.get(`/asistencia-materia/${course.value}/${day.value}`)).data;if(!subject.value)subject.value=sheet.value.materias[0]?.id||'';fillRows()}
 catch(e){error.value=message(e)}finally{busy.value=false}
}
watch(hour,()=>{if(sheet.value)fillRows()})
async function save(){
 saving.value=true;error.value='';notice.value=''
 try{
  const body={materia_id:Number(subject.value),dictada:dictada.value,motivo_correccion:reason.value.trim()||null,
   estudiantes:dictada.value?rows.value.map(r=>({matricula_id:r.matricula_id,estado:r.estado,justificada:r.estado==='PRESENTE'?null:r.justificada,observacion:r.observacion?.trim()||null})):[]}
  sheet.value=(await api.put(`/asistencia-materia/${sheet.value.curso_id}/${sheet.value.fecha}/${hour.value}`,body)).data
  fillRows();notice.value=`Hora ${hour.value} guardada.`
 }catch(e){error.value=message(e)}finally{saving.value=false}
}
async function loadDetail(){
 if(!student.value)return
 busy.value=true;error.value='';detail.value=null
 try{
  detail.value=(await api.get(`/asistencia-materia/matricula/${student.value}/desglose`)).data
  guardians.value=(await api.get(`/citaciones/apoderados/${student.value}`)).data
  summon.value.apoderado_id=guardians.value[0]?.id||''
 }catch(e){error.value=message(e)}finally{busy.value=false}
}
async function createSummon(){
 saving.value=true;error.value='';notice.value=''
 try{
  const s=summon.value
  const body={matricula_id:Number(student.value),apoderado_id:Number(s.apoderado_id),fecha_programada:s.fecha_programada,motivo:s.motivo.trim(),origen:s.origen,
   materia_id:s.origen==='DOCENTE_MATERIA'?Number(s.materia_id):null}
  const r=(await api.post('/citaciones',body)).data;delete r.id;detail.value=r
  summon.value={...summon.value,motivo:''};notice.value='Citación registrada.'
 }catch(e){error.value=message(e)}finally{saving.value=false}
}
const cards=computed(()=>{const i=detail.value?.indicadores;if(!i)return []
 return [['Asistencia media por materia',pct(i.asistencia_materia_media),'Cada materia pesa igual, sin importar cuántas clases tiene por semana.'],
  ['Materia con menor asistencia',pct(i.asistencia_materia_minima),''],
  [`Materias bajo ${pct(detail.value.umbral)}`,i.materias_asistencia_baja??'—','Criterio técnico inicial, a validar con Dirección.'],
  ['Días con licencia parcial',i.dias_licencia_parcial??'—','Asistió a una o más horas y luego se retiró con licencia.'],
  ['Citaciones',i.citaciones_total,`Dirección ${i.citaciones_direccion} · Orientación ${i.citaciones_orientacion} · Docentes ${i.citaciones_docente_materia}`],
  ['Máximo en una materia',i.citaciones_max_una_materia,`${i.materias_con_citacion} materia(s) con citación`]]})
onMounted(loadCourses)
</script>
<template>
 <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
  <p class="text-xs text-blue-600 dark:text-blue-400 uppercase tracking-widest font-semibold mb-2">Registro escolar</p>
  <h1 class="text-3xl font-bold">Asistencia por materia</h1>
  <div class="flex flex-wrap gap-2 mt-5 border-b border-slate-200 dark:border-slate-700" role="tablist">
   <button v-for="[k,l] in [['registro','Registrar por hora'],['desglose','Desglose por estudiante']]" :key="k" role="tab" :aria-selected="tab===k" @click="tab=k"
    class="px-4 py-2 -mb-px border-b-2 text-sm font-medium" :class="tab===k?'border-blue-600 text-blue-700 dark:text-blue-300':'border-transparent text-slate-500'">{{ l }}</button>
  </div>
  <form @submit.prevent="load" class="flex flex-wrap items-end gap-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 my-6">
   <label class="flex-1 min-w-48 text-sm font-medium">Curso<select v-model="course" required class="field" :disabled="busy||saving" @change="sheet=null;detail=null;student=''"><option value="" disabled>Selecciona un curso</option><option v-for="c in courses" :key="c.id" :value="c.id">{{ c.nombre }}</option></select></label>
   <label class="text-sm font-medium">Fecha<input v-model="day" type="date" required :max="today()" class="field" :disabled="busy||saving" /></label>
   <button class="primary" :disabled="busy||saving||!course">{{ busy?'Cargando…':'Consultar' }}</button>
  </form>
  <p v-if="error" role="alert" class="bg-red-50 text-red-800 border border-red-200 rounded-xl p-4 mb-5">{{ error }}</p>
  <p v-if="notice" role="status" class="bg-green-50 text-green-800 border border-green-200 rounded-xl p-4 mb-5">{{ notice }}</p>

  <template v-if="sheet&&tab==='registro'">
   <p v-if="!sheet.es_lectiva" class="p-5 rounded-xl bg-amber-50 text-amber-900">Ese día está registrado como día sin clases.</p>
   <template v-else>
    <div class="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 mb-5">
     <p class="text-sm font-semibold">Horario registrado · {{ sheet.curso }} · {{ sheet.fecha }}</p>
     <div class="flex flex-wrap gap-2 mt-3">
      <button v-for="h in 8" :key="h" type="button" @click="hour=h" class="px-3 py-2 rounded-lg border text-xs text-left min-w-28"
       :class="Number(hour)===h?'border-blue-600 bg-blue-50 dark:bg-blue-950/40':'border-slate-300 dark:border-slate-600'">
       <span class="font-semibold">{{ h }}.ª hora</span><span class="block text-slate-500">{{ sheet.sesiones.find(s=>s.periodo===h)?.materia || 'Sin registrar' }}{{ sheet.sesiones.find(s=>s.periodo===h&&!s.dictada)?' · no dictada':'' }}</span>
      </button>
     </div>
    </div>
    <div class="flex flex-wrap items-end gap-4 mb-5">
     <label class="text-sm font-medium min-w-56">Materia de la {{ hour }}.ª hora<select v-model="subject" class="field" :disabled="saving||(existing&&Object.keys(session.registros).length>0)"><option value="" disabled>Selecciona</option><option v-for="m in sheet.materias" :key="m.id" :value="m.id">{{ m.nombre }}</option></select></label>
     <label class="flex gap-2 items-center text-sm font-medium pb-3"><input v-model="dictada" type="checkbox" :disabled="saving" /> La clase se dictó</label>
    </div>
    <p v-if="!sheet.materias.length" class="p-4 mb-5 rounded-xl bg-amber-50 text-amber-900 text-sm">Este curso no tiene materias asignadas{{ docente?' a tu nombre':'' }}. Dirección debe registrar las asignaciones docentes.</p>
    <p v-if="!dictada" class="p-4 mb-5 rounded-xl bg-slate-100 dark:bg-slate-900 text-sm">Una clase no dictada no lleva asistencia y no cuenta en el porcentaje de la materia.</p>
    <div v-else class="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
     <div class="overflow-x-auto"><table class="w-full text-left text-sm"><thead class="bg-slate-50 dark:bg-slate-900/40 text-slate-500 dark:text-slate-300"><tr><th class="cell">Estudiante</th><th class="cell">Estado en esta hora</th><th class="cell">Justificación</th><th class="cell">Observación</th></tr></thead>
      <tbody class="divide-y divide-slate-100 dark:divide-slate-700"><tr v-for="r in rows" :key="r.matricula_id">
       <td class="cell min-w-44 font-medium">{{ nombreEstudiante(r) }}</td>
       <td class="cell"><select v-model="r.estado" class="field min-w-32" :disabled="saving" :aria-label="`Estado de ${nombreEstudiante(r)}`"><option v-for="[v,l] in statuses" :key="v" :value="v">{{ l }}</option></select></td>
       <td class="cell"><select v-model="r.justificada" class="field min-w-32" :disabled="saving||r.estado==='PRESENTE'" :aria-label="`Justificación de ${nombreEstudiante(r)}`"><option :value="null">{{ r.estado==='PRESENTE'?'No corresponde':'Sin confirmar' }}</option><option :value="true">Justificada</option><option :value="false">Injustificada</option></select></td>
       <td class="cell"><input v-model="r.observacion" maxlength="500" class="field min-w-44" placeholder="Opcional" :disabled="saving" /></td>
      </tr><tr v-if="!rows.length"><td colspan="4" class="p-8 text-center text-slate-500">No hay estudiantes con matrícula vigente en esta fecha.</td></tr></tbody></table></div>
    </div>
    <label v-if="existing" class="block mt-5 text-sm font-medium">Motivo de corrección<input v-model="reason" maxlength="500" placeholder="Obligatorio si modificas una hora ya registrada" class="field" :disabled="saving" /></label>
    <div class="flex justify-end mt-5"><button class="primary" :disabled="saving||!subject||(dictada&&!rows.length)" @click="save">{{ saving?'Guardando…':`Guardar ${hour}.ª hora` }}</button></div>
   </template>
  </template>

  <template v-if="sheet&&tab==='desglose'">
   <div class="flex flex-wrap items-end gap-4 mb-5">
    <label class="text-sm font-medium min-w-64">Estudiante<select v-model="student" class="field" @change="loadDetail"><option value="" disabled>Selecciona un estudiante</option><option v-for="s in sheet.estudiantes" :key="s.matricula_id" :value="s.matricula_id">{{ nombreEstudiante(s) }}</option></select></label>
   </div>
   <template v-if="detail">
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-5">
     <div v-for="[l,v,d] in cards" :key="l" class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-4"><p class="text-xs text-slate-500">{{ l }}</p><p class="text-2xl font-bold mt-1">{{ v }}</p><p v-if="d" class="text-xs text-slate-500 mt-1">{{ d }}</p></div>
    </div>
    <div class="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden mb-6">
     <p class="p-4 text-sm font-semibold border-b border-slate-200 dark:border-slate-700">Asistencia por materia: clases asistidas ÷ clases registradas de esa materia</p>
     <div class="overflow-x-auto"><table class="w-full text-left text-sm"><thead class="bg-slate-50 dark:bg-slate-900/40 text-slate-500 dark:text-slate-300"><tr><th class="cell">Materia</th><th class="cell">Clases dictadas</th><th class="cell">Asistió</th><th class="cell">Faltas</th><th class="cell">Licencias</th><th class="cell">% asistencia</th><th class="cell">Citaciones</th></tr></thead>
      <tbody class="divide-y divide-slate-100 dark:divide-slate-700"><tr v-for="f in detail.materias" :key="f.materia_id">
       <td class="cell font-medium">{{ f.materia }}</td><td class="cell">{{ f.dictadas }}</td><td class="cell">{{ f.presentes+f.atrasos }}<span v-if="f.atrasos" class="text-xs text-slate-500"> ({{ f.atrasos }} con atraso)</span></td>
       <td class="cell">{{ f.faltas }}</td><td class="cell">{{ f.licencias }}</td>
       <td class="cell"><div class="flex items-center gap-2"><div class="h-2 w-24 rounded bg-slate-100 dark:bg-slate-700"><div class="h-2 rounded" :class="f.baja?'bg-red-500':'bg-emerald-500'" :style="{width:`${Math.round((f.porcentaje||0)*100)}%`}"></div></div><span :class="f.baja?'text-red-600 font-semibold':''">{{ pct(f.porcentaje) }}</span></div></td>
       <td class="cell">{{ f.citaciones }}</td>
      </tr><tr v-if="!detail.materias.length"><td colspan="7" class="p-8 text-center text-slate-500">Todavía no hay asistencia por materia registrada para este estudiante.</td></tr></tbody></table></div>
    </div>
    <div class="grid lg:grid-cols-2 gap-6">
     <div class="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
      <p class="text-sm font-semibold">Citaciones registradas</p>
      <ul class="mt-2 text-sm divide-y divide-slate-100 dark:divide-slate-700"><li v-for="(c,i) in detail.citaciones" :key="i" class="py-2">{{ String(c.fecha).slice(0,10) }} · {{ {DOCENTE_MATERIA:`Docente · ${c.materia}`,DIRECCION:'Dirección',ORIENTACION:'Orientación'}[c.origen] }} · {{ c.estado }}</li>
       <li v-if="!detail.citaciones.length" class="py-2 text-slate-500">Sin citaciones registradas.</li></ul>
     </div>
     <form class="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 space-y-3" @submit.prevent="createSummon">
      <p class="text-sm font-semibold">Registrar citación</p>
      <p v-if="!guardians.length" class="text-sm text-amber-700 dark:text-amber-300">El estudiante no tiene apoderado registrado: no se puede programar una citación.</p>
      <label class="block text-sm">Origen<select v-model="summon.origen" class="field"><option v-for="[v,l] in origins" :key="v" :value="v">{{ l }}</option></select></label>
      <label v-if="summon.origen==='DOCENTE_MATERIA'" class="block text-sm">Materia<select v-model="summon.materia_id" required class="field"><option value="" disabled>Selecciona</option><option v-for="m in sheet.materias" :key="m.id" :value="m.id">{{ m.nombre }}</option></select></label>
      <label class="block text-sm">Apoderado<select v-model="summon.apoderado_id" required class="field"><option v-for="a in guardians" :key="a.id" :value="a.id">{{ a.nombre }}</option></select></label>
      <label class="block text-sm">Fecha y hora<input v-model="summon.fecha_programada" type="datetime-local" required class="field" /></label>
      <label class="block text-sm">Motivo<input v-model="summon.motivo" required minlength="3" maxlength="2000" class="field" placeholder="Ej.: inasistencias en la materia" /></label>
      <div class="flex justify-end"><button class="primary" :disabled="saving||!guardians.length">Registrar citación</button></div>
     </form>
    </div>
   </template>
  </template>
 </section>
</template>
<style scoped>
.field{@apply block w-full mt-1 px-3 py-2.5 text-sm rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50;}
.primary{@apply px-4 py-2.5 rounded-lg bg-blue-600 text-white font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed;}
.cell{@apply px-4 py-3;}
</style>
