<script setup>
defineProps({ titulo: { type: String, default: '¿Cómo se lee?' } })
</script>
<template>
 <details class="text-sm">
  <summary class="cursor-pointer w-fit text-blue-700 dark:text-blue-300 hover:underline">{{ titulo }}</summary>
  <div class="mt-2 max-w-4xl space-y-2 rounded-xl border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40 text-blue-900 dark:text-blue-100 p-4"><slot /></div>
 </details>
</template>
