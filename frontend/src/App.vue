<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import ConfirmDialog from '@/components/common/ConfirmDialog.vue'
import { useThemeStore } from '@/stores/themeStore'

const themeStore = useThemeStore()
</script>

<template>
  <div :class="{ dark: themeStore.isDark }">
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
    <ToastContainer />
    <ConfirmDialog />
  </div>
</template>
