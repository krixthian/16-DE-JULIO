<script setup>
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import Sidebar from './components/Sidebar.vue'

const route = useRoute()
const isLoginRoute = computed(() => route.path === '/login')
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-slate-900 transition-colors duration-300 flex">
    
    <Sidebar v-if="!isLoginRoute" />
    
    <main class="flex-grow min-w-0 h-screen overflow-y-auto">
      <RouterView />
    </main>

  </div>
</template>

<style scoped>
</style>
