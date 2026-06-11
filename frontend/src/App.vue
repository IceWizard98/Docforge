<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
</script>

<template>
  <RouterView v-slot="{ Component, route }">
    <template v-if="route.meta?.layout === false">
      <component :is="Component" />
    </template>
    <template v-else>
      <AppShell>
        <keep-alive :include="['DocumentView']">
          <component :is="Component" :key="route.path" />
        </keep-alive>
      </AppShell>
    </template>
  </RouterView>
</template>
