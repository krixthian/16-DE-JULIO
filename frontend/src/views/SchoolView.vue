<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import api from '../services/api'

const props = defineProps({ section: { type: String, required: true } })
const sections = {
  materias: { title:'Materias', singular:'materia', description:'Mantén el catálogo de materias que se imparten en primaria.', columns:[['nombre','Nombre'],['sigla','Sigla']] },
  asignaciones: { title:'Asignaciones docentes', singular:'asignación', description:'Define quién imparte cada materia en un curso y durante qué fechas.', columns:[['gestion_anio','Gestión'],['curso_nombre','Curso'],['materia_nombre','Materia'],['docente_nombre','Docente'],['vigente_desde','Desde'],['vigente_hasta','Hasta'],['estado','Estado']] },
  gestiones: { title: 'Gestiones escolares', singular: 'gestión', description: 'Define el calendario de cada año para organizar los cursos y las matrículas.', columns: [['anio','Año'],['fecha_inicio','Inicio'],['fecha_fin','Fin'],['calendario','Calendario']] },
  cursos: { title: 'Cursos', singular: 'curso', description: 'Organiza los grados y paralelos de primaria en cada gestión.', columns: [['gestion_anio','Gestión'],['grado','Grado'],['paralelo','Paralelo'],['docente_nombre','Docente asesor']] },
  estudiantes: { title: 'Estudiantes', singular: 'estudiante', description: 'Registra los datos del estudiante. Su curso e historial se conservan en las matrículas.', columns: [['apellido','Apellidos'],['nombre','Nombres'],['codigo_rude','RUDE'],['fecha_nacimiento','Nacimiento'],['matriculas','Matrículas']] },
  matriculas: { title: 'Matrículas', singular: 'matrícula', description: 'Vincula a cada estudiante con un curso y conserva sus fechas de permanencia.', columns: [['estudiante_nombre','Estudiante'],['gestion_anio','Gestión'],['curso_nombre','Curso'],['fecha_ingreso','Ingreso'],['fecha_fin','Fin del segmento'],['origen','Datos'],['estado','Estado']] },
}
const config = computed(() => sections[props.section])
const data = ref({ gestiones: [], cursos: [], estudiantes: [], matriculas: [], docentes: [], materias: [], asignaciones: [] })
const loading = ref(true), saving = ref(false), error = ref(''), notice = ref('')
const query = ref(''), year = ref(''), page = ref(1), modal = ref(false), editing = ref(null), form = ref({})
const dialog = ref(null)
let previousFocus = null
watch(modal, async (opened) => {
  if (opened) {
    previousFocus = document.activeElement
    await nextTick()
    dialog.value?.querySelector('input:not(:disabled), select:not(:disabled), button')?.focus()
  } else previousFocus?.focus?.()
})
function trapFocus(event) {
  if (event.key !== 'Tab') return
  const fields = [...dialog.value.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), a[href]')]
  const first = fields[0], last = fields.at(-1)
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}
let requestId = 0
function message(e) {
  const detail = e.response?.data?.detail
  if (Array.isArray(detail)) return detail.map(x => `${x.loc?.slice(1).join('.') || 'Campo'}: ${x.msg.replace('Value error, ', '')}`).join(' · ')
  return typeof detail === 'string' ? detail : 'No se pudo conectar con el servidor. Verifica que el backend esté iniciado e inténtalo de nuevo.'
}
async function load() {
  const id = ++requestId
  loading.value = true; error.value = ''
  try {
    const names = ['gestiones','cursos','estudiantes','matriculas','docentes','materias','asignaciones']
    const responses = await Promise.all(names.map(name => api.get(`/escolar/${name}`)))
    if (id !== requestId) return
    data.value = Object.fromEntries(names.map((name, i) => [name, responses[i].data]))
  } catch(e) { if (id === requestId) error.value = message(e) }
  finally { if (id === requestId) loading.value = false }
}
watch(() => props.section, () => { modal.value=false; query.value=''; year.value=''; page.value=1; notice.value=''; load() }, { immediate: true })
watch([query, year], () => { page.value=1 })
const rows = computed(() => data.value[props.section].filter(row => {
  const matchesYear = !year.value || String(row.gestion_anio ?? row.anio) === year.value
  const matchesText = !query.value || Object.values(row).some(v => String(v ?? '').toLocaleLowerCase().includes(query.value.toLocaleLowerCase()))
  return matchesYear && matchesText
}))
const pages = computed(() => Math.max(1, Math.ceil(rows.value.length / 15)))
const visible = computed(() => rows.value.slice((Math.min(page.value,pages.value)-1)*15, Math.min(page.value,pages.value)*15))
const incomplete = computed(() => data.value.gestiones.filter(g => !g.fecha_inicio || !g.fecha_fin))
const availableCourses = computed(() => data.value.cursos.filter(c => !form.value.gestion_id || c.gestion_id === Number(form.value.gestion_id)))
const canCreate = computed(() => props.section === 'asignaciones' ? data.value.cursos.length > 0 && data.value.materias.length > 0 && data.value.docentes.length > 0 : props.section === 'cursos' ? data.value.gestiones.length > 0 : props.section === 'matriculas' ? data.value.cursos.length > 0 && data.value.estudiantes.length > 0 : true)
function display(row, key) {
  if (key==='vigente_hasta' && !row[key]) return 'Fin de gestión'
  if (key==='docente_nombre' && row.docente_activo === false) return `${row[key]} (inactivo)`
  if (key==='calendario') return row.fecha_inicio && row.fecha_fin ? 'Completo' : 'Fechas pendientes'
  if (key==='matriculas') return data.value.matriculas.filter(m => m.estudiante_id === row.id).length || 'Sin matrícula'
  if (key==='grado') return `${row[key]}° de primaria`
  if (key==='fecha_fin' && props.section==='matriculas' && !row[key]) return 'Hasta fin de gestión'
  if (key==='origen') return row[key] === 'REAL' ? 'Reales' : 'Simulados'
  if (key==='estado') return { VIGENTE:'Vigente', FINALIZADA:'Finalizada', PROGRAMADA:'Programada' }[row[key]]
  return row[key] || '—'
}
function open(row=null) {
  error.value=''; notice.value=''; editing.value=row?.id ?? null
  if (row) {
    form.value={...row}
    if (['matriculas','asignaciones'].includes(props.section)) form.value.gestion_id=data.value.cursos.find(c=>c.id===row.curso_id)?.gestion_id ?? ''
  } else {
    form.value = {
      materias: { nombre:'', sigla:'' },
      asignaciones: {gestion_id:data.value.gestiones[0]?.id ?? '', curso_id:'', materia_id:'', docente_id:'', vigente_desde:'', vigente_hasta:''},
      gestiones: { anio: new Date().getFullYear(), fecha_inicio:'', fecha_fin:'' },
      cursos: { gestion_id: data.value.gestiones[0]?.id ?? '', grado:1, paralelo:'', docente_asesor_id:'' },
      estudiantes: { nombre:'', apellido:'', codigo_rude:'', fecha_nacimiento:'' },
      matriculas: { gestion_id:data.value.gestiones[0]?.id ?? '', estudiante_id:'', curso_id:'', fecha_ingreso:'', fecha_fin:'', origen:'' },
    }[props.section]
  }
  modal.value=true
}
function close() { if (!saving.value) { modal.value=false; error.value='' } }
function payload() {
  const f=form.value
  if (props.section==='materias') return {nombre:f.nombre.trim(),sigla:f.sigla?.trim() || null}
  if (props.section==='asignaciones') return {curso_id:Number(f.curso_id),materia_id:Number(f.materia_id),docente_id:Number(f.docente_id),vigente_desde:f.vigente_desde,vigente_hasta:f.vigente_hasta || null}
  if (props.section==='gestiones') return { anio:Number(f.anio), fecha_inicio:f.fecha_inicio, fecha_fin:f.fecha_fin }
  if (props.section==='cursos') return { gestion_id:Number(f.gestion_id), grado:Number(f.grado), paralelo:f.paralelo.trim(), docente_asesor_id:f.docente_asesor_id ? Number(f.docente_asesor_id) : null }
  if (props.section==='estudiantes') return { nombre:f.nombre.trim(), apellido:f.apellido.trim(), codigo_rude:f.codigo_rude?.trim() || null, fecha_nacimiento:f.fecha_nacimiento || null }
  return { estudiante_id:Number(f.estudiante_id), curso_id:Number(f.curso_id), fecha_ingreso:f.fecha_ingreso, fecha_fin:f.fecha_fin || null, origen:f.origen }
}
async function save() {
  if (saving.value) return
  saving.value=true; error.value=''
  try {
    const url=`/escolar/${props.section}`
    if (editing.value) await api.put(`${url}/${editing.value}`,payload())
    else await api.post(url,payload())
    modal.value=false; notice.value='Registro guardado correctamente.'
    await load()
  } catch(e) { error.value=message(e) }
  finally { saving.value=false }
}
</script>

<template>
  <section class="p-4 md:p-8 max-w-7xl mx-auto text-slate-900 dark:text-slate-100">
    <p class="text-xs uppercase tracking-widest font-semibold text-blue-600 dark:text-blue-400 mb-2">Administración escolar</p>
    <div class="flex flex-wrap justify-between items-start gap-4 mb-7">
      <div><h1 class="text-3xl font-bold">{{ config.title }}</h1><p class="text-slate-500 dark:text-slate-400 mt-2 max-w-2xl">{{ config.description }}</p></div>
      <button class="primary" :disabled="loading || !canCreate" @click="open()">+ Registrar {{ config.singular }}</button>
    </div>
    <nav aria-label="Módulos escolares" class="flex flex-wrap gap-2 mb-6">
      <RouterLink v-for="(item,key) in sections" :key="key" :to="`/escolar/${key}`" class="px-4 py-2 rounded-lg text-sm border" :class="key === section ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'">{{ item.title }}</RouterLink>
    </nav>
    <div v-if="notice" role="status" class="mb-4 rounded-lg bg-green-50 text-green-800 border border-green-200 p-3">{{ notice }}</div>
    <div v-if="error && !modal" role="alert" class="mb-4 rounded-lg bg-red-50 text-red-800 p-3">{{ error }} <button class="underline ml-2" @click="load">Reintentar</button></div>
    <div v-if="incomplete.length && ['gestiones','matriculas','asignaciones'].includes(section)" class="mb-5 p-4 rounded-xl bg-amber-50 text-amber-900 border border-amber-200">
      Completa las fechas de {{ incomplete.map(g=>g.anio).join(', ') }} en <RouterLink to="/escolar/gestiones" class="font-semibold underline">Gestiones</RouterLink> antes de registrar matrículas o asignaciones.
    </div>
    <div v-if="!loading && !canCreate" class="mb-5 text-slate-500">{{ section==='asignaciones' ? 'Necesitas un curso, una materia y un usuario Docente activo para crear una asignación.' : section==='cursos' ? 'Registra una gestión para crear cursos.' : 'Registra al menos un estudiante y un curso para matricular.' }}</div>
    <div class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
      <div class="p-4 flex flex-wrap items-center gap-3 border-b border-slate-200 dark:border-slate-700">
        <label class="flex-1 min-w-48"><span class="sr-only">Buscar registros</span><input v-model="query" type="search" placeholder="Buscar en los registros…" class="field" /></label>
        <label v-if="!['estudiantes','materias'].includes(section)"><span class="sr-only">Filtrar por gestión</span><select v-model="year" class="field"><option value="">Todas las gestiones</option><option v-for="g in data.gestiones" :key="g.id" :value="String(g.anio)">{{ g.anio }}</option></select></label>
        <span class="text-sm text-slate-500">{{ rows.length }} registros</span>
      </div>
      <p v-if="loading" role="status" class="p-10 text-center text-slate-500">Cargando registros…</p>
      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="bg-slate-50 dark:bg-slate-900/40 text-slate-500 dark:text-slate-300"><tr><th v-for="[key,label] in config.columns" :key="key" class="px-4 py-3 font-semibold whitespace-nowrap" scope="col">{{ label }}</th><th class="px-4 py-3" scope="col">Acciones</th></tr></thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-700">
            <tr v-for="row in visible" :key="row.id" class="hover:bg-slate-50 dark:hover:bg-slate-700/30"><td v-for="[key] in config.columns" :key="key" class="px-4 py-4 whitespace-nowrap">{{ display(row,key) }}</td><td class="px-4 py-4"><button class="text-blue-600 dark:text-blue-400 font-semibold hover:underline" :aria-label="`Editar ${config.singular} ${row.nombre || row.anio || row.estudiante_nombre || row.id}`" @click="open(row)">Editar</button></td></tr>
            <tr v-if="!visible.length"><td :colspan="config.columns.length+1" class="text-center text-slate-500 p-10">{{ query || year ? 'No hay resultados para estos filtros.' : `Todavía no hay registros. Usa «Registrar ${config.singular}» para comenzar.` }}</td></tr>
          </tbody>
        </table>
        <div class="p-4 flex justify-between items-center border-t border-slate-200 dark:border-slate-700 text-sm"><button class="secondary" :disabled="page<=1" @click="page--">Anterior</button><span>Página {{ Math.min(page,pages) }} de {{ pages }}</span><button class="secondary" :disabled="page>=pages" @click="page++">Siguiente</button></div>
      </div>
    </div>

    <div v-if="modal" class="fixed inset-0 z-50 bg-slate-950/60 flex items-center justify-center p-4" @click.self="close" @keydown.esc="close">
      <section ref="dialog" role="dialog" aria-modal="true" aria-labelledby="form-title" @keydown="trapFocus" class="bg-white dark:bg-slate-800 w-full max-w-xl rounded-2xl shadow-xl max-h-[90vh] overflow-y-auto p-6">
        <div class="flex justify-between items-center mb-5"><h2 id="form-title" class="text-xl font-bold">{{ editing ? 'Editar' : 'Registrar' }} {{ config.singular }}</h2><button type="button" aria-label="Cerrar formulario" class="text-2xl px-2" :disabled="saving" @click="close">×</button></div>
        <form @submit.prevent="save" class="space-y-4">
          <template v-if="section==='materias'">
            <label class="label">Nombre de la materia<input v-model="form.nombre" required maxlength="120" placeholder="Ej.: Matemática" class="field" /></label>
            <label class="label">Sigla (opcional)<input v-model="form.sigla" maxlength="20" placeholder="Ej.: MAT" class="field" /></label>
          </template>
          <template v-if="section==='asignaciones'">
            <label class="label">Gestión<select v-model.number="form.gestion_id" required class="field" @change="form.curso_id='' "><option value="" disabled>Selecciona una gestión</option><option v-for="g in data.gestiones" :key="g.id" :value="g.id">{{ g.anio }}{{ !g.fecha_inicio || !g.fecha_fin ? ' · Fechas pendientes' : '' }}</option></select></label>
            <label class="label">Curso<select v-model.number="form.curso_id" required class="field"><option value="" disabled>Selecciona un curso</option><option v-for="c in availableCourses" :key="c.id" :value="c.id">{{ c.grado }}° {{ c.paralelo }}</option></select></label>
            <label class="label">Materia<select v-model.number="form.materia_id" required class="field"><option value="" disabled>Selecciona una materia</option><option v-for="m in data.materias" :key="m.id" :value="m.id">{{ m.nombre }}</option></select></label>
            <label class="label">Docente<select v-model.number="form.docente_id" required class="field"><option value="" disabled>Selecciona un docente activo</option><option v-if="editing && !data.docentes.some(d=>d.id===form.docente_id)" :value="form.docente_id">{{ form.docente_nombre }} · Solo cierre de asignación</option><option v-for="d in data.docentes" :key="d.id" :value="d.id">{{ d.apellido }}, {{ d.nombre }}</option></select></label>
            <label class="label">Vigente desde<input v-model="form.vigente_desde" type="date" required class="field" /></label>
            <label class="label">Vigente hasta (opcional)<input v-model="form.vigente_hasta" type="date" :min="form.vigente_desde" class="field" /></label>
            <p class="text-sm text-slate-500">Sin fecha final, la asignación dura hasta el cierre de la gestión. Cada materia tiene un docente responsable por curso en un período. Para un reemplazo, finaliza la asignación anterior y registra otra desde una fecha posterior.</p>
          </template>
          <template v-if="section==='gestiones'">
            <label class="label">Año<input v-model.number="form.anio" type="number" min="1900" max="2100" required class="field" /></label>
            <label class="label">Inicio de clases<input v-model="form.fecha_inicio" type="date" required class="field" /></label>
            <label class="label">Fin de la gestión<input v-model="form.fecha_fin" type="date" :min="form.fecha_inicio" required class="field" /></label>
          </template>
          <template v-if="section==='cursos'">
            <label class="label">Gestión<select v-model.number="form.gestion_id" required class="field"><option value="" disabled>Selecciona una gestión</option><option v-for="g in data.gestiones" :key="g.id" :value="g.id">{{ g.anio }}</option></select></label>
            <label class="label">Grado de primaria<select v-model.number="form.grado" required class="field"><option v-for="n in 6" :key="n" :value="n">{{ n }}° de primaria</option></select></label>
            <label class="label">Paralelo<input v-model="form.paralelo" maxlength="5" pattern="[A-Za-z0-9]+" placeholder="Ej.: A" required class="field" /></label>
            <label class="label">Docente asesor (opcional)<select v-model="form.docente_asesor_id" class="field"><option value="">Sin asignar</option><option v-if="form.docente_asesor_id && !data.docentes.some(d=>d.id===Number(form.docente_asesor_id))" :value="form.docente_asesor_id">Docente no disponible: selecciona otro</option><option v-for="d in data.docentes" :key="d.id" :value="d.id">{{ d.nombre }} {{ d.apellido }}</option></select></label>
          </template>
          <template v-if="section==='estudiantes'">
            <label class="label">Nombres<input v-model="form.nombre" maxlength="100" required class="field" autocomplete="off" /></label>
            <label class="label">Apellidos<input v-model="form.apellido" maxlength="100" required class="field" autocomplete="off" /></label>
            <label class="label">RUDE (opcional)<input v-model="form.codigo_rude" maxlength="50" class="field" /></label>
            <label class="label">Fecha de nacimiento (opcional)<input v-model="form.fecha_nacimiento" type="date" :max="new Date().toLocaleDateString('en-CA')" class="field" /></label>
            <p class="text-sm text-slate-500">El código interno se genera automáticamente. Después puedes registrar la matrícula del estudiante.</p>
          </template>
          <template v-if="section==='matriculas'">
            <label class="label">Estudiante<select v-model.number="form.estudiante_id" :disabled="!!editing" required class="field"><option value="" disabled>Selecciona un estudiante</option><option v-for="s in data.estudiantes" :key="s.id" :value="s.id">{{ s.apellido }}, {{ s.nombre }} · {{ s.codigo_rude || s.codigo_anonimo }}</option></select></label>
            <label class="label">Gestión<select v-model.number="form.gestion_id" :disabled="!!editing" required class="field" @change="form.curso_id='' "><option value="" disabled>Selecciona una gestión</option><option v-for="g in data.gestiones" :key="g.id" :value="g.id">{{ g.anio }}{{ !g.fecha_inicio || !g.fecha_fin ? ' · Fechas pendientes' : '' }}</option></select></label>
            <label class="label">Curso<select v-model.number="form.curso_id" :disabled="!!editing" required class="field"><option value="" disabled>Selecciona un curso</option><option v-for="c in availableCourses" :key="c.id" :value="c.id">{{ c.grado }}° {{ c.paralelo }}</option></select></label>
            <label class="label">Fecha de ingreso<input v-model="form.fecha_ingreso" type="date" required class="field" /></label>
            <label class="label">Fecha final del segmento (opcional)<input v-model="form.fecha_fin" type="date" :min="form.fecha_ingreso" class="field" /></label>
            <p class="text-sm text-slate-500">Déjala vacía si permanece hasta el cierre de la gestión. Cerrar un segmento no confirma un abandono escolar.</p>
            <label class="label">Origen de los datos<select v-model="form.origen" required class="field"><option value="" disabled>Selecciona el origen</option><option value="REAL">Reales</option><option value="SIMULADO">Simulados para pruebas</option></select></label>
            <p v-if="editing" class="text-sm text-slate-500">Para un cambio de curso, finaliza este segmento y registra otra matrícula desde una fecha posterior.</p>
          </template>
          <p v-if="error" role="alert" class="rounded-lg bg-red-50 text-red-800 p-3 text-sm">{{ error }}</p>
          <div class="flex justify-end gap-3 pt-4"><button type="button" class="secondary" :disabled="saving" @click="close">Cancelar</button><button type="submit" class="primary" :disabled="saving">{{ saving ? 'Guardando…' : 'Guardar' }}</button></div>
        </form>
      </section>
    </div>
  </section>
</template>

<style scoped>
.field { @apply block w-full mt-1 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60; }
.label { @apply block text-sm font-medium; }
.primary { @apply px-4 py-2.5 bg-blue-600 text-white rounded-lg font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed; }
.secondary { @apply px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-sm hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed; }
</style>
