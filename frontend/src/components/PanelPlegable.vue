<script setup>
import { ref } from 'vue'
const props = defineProps({ titulo: { type: String, required: true }, resumen: { type: String, default: '' }, abierto: Boolean })
const open = ref(props.abierto)
</script>
<template>
 <article class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
  <h2><button type="button" @click="open=!open" :aria-expanded="open" class="w-full flex items-center justify-between gap-4 p-4 text-left">
   <span><span class="font-semibold">{{ titulo }}</span><span v-if="resumen" class="block text-sm text-slate-500">{{ resumen }}</span></span>
   <span class="text-slate-400 transition-transform" :class="open?'rotate-180':''" aria-hidden="true">▾</span>
  </button></h2>
  <div v-if="open" class="px-5 pb-5 text-sm"><slot /></div>
 </article>
</template>
