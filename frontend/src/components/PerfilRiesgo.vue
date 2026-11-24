<script setup>
defineProps({ colores: { type: Object, required: true }, grande: Boolean, soloAlertas: Boolean })
const TONO = {
  ROJO: ['bg-red-100 text-red-800 border-red-300 dark:bg-red-900/40 dark:text-red-200 dark:border-red-800', 'bg-red-600', 'rojo'],
  AMARILLO: ['bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-900/40 dark:text-amber-200 dark:border-amber-800', 'bg-amber-500', 'amarillo'],
  VERDE: ['bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-900', 'bg-emerald-500', 'verde'],
  null: ['bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-900 dark:text-slate-400 dark:border-slate-700', 'bg-slate-400', 'sin dato'],
}
const ACCION = { Académica: 'Reforzamiento en sus áreas', Desempeño: 'Apoyo del docente en actividades', Actitud: 'Conversación y orientación', Asistencia: 'Contacto con la familia' }
const tono = c => TONO[c] || TONO.null
</script>
<template>
 <div v-if="grande" class="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
  <div v-for="(c, d) in colores" :key="d" class="rounded-lg border p-3" :class="tono(c)[0]">
   <p class="font-semibold text-sm flex items-center gap-2"><span class="h-2.5 w-2.5 rounded-full" :class="tono(c)[1]" aria-hidden="true"></span>{{ d }}</p>
   <p class="text-xs mt-1">{{ tono(c)[2] }}<template v-if="c === 'ROJO' || c === 'AMARILLO'"> · {{ ACCION[d] }}</template></p>
  </div>
 </div>
 <ul v-else class="flex flex-wrap gap-1 max-w-[15rem]">
  <li v-for="(c, d) in soloAlertas ? Object.fromEntries(Object.entries(colores).filter(([, x]) => x === 'ROJO' || x === 'AMARILLO')) : colores" :key="d" class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px]" :class="tono(c)[0]" :title="`${d}: ${tono(c)[2]}`"><span class="h-1.5 w-1.5 rounded-full" :class="tono(c)[1]" aria-hidden="true"></span>{{ d }}<span class="sr-only">: {{ tono(c)[2] }}</span></li>
 </ul>
</template>
