<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView, useRouter } from 'vue-router'
import { useAuthStore } from '@/api/authStore'

const auth = useAuthStore()
const router = useRouter()

onMounted(() => {
  auth.checkToken()
})
</script>

<template>
  <div class="h-screen w-screen bg-surface text-foreground overflow-hidden">
    <RouterView />
  </div>
</template>
