<template>
  <div id="app">
    <nav class="nav-bar" v-if="showNav">
      <div class="nav-brand">货车宝会议关键事项追踪</div>
      <div class="nav-links">
        <router-link to="/kanban">看板</router-link>
        <router-link to="/import">导入会议</router-link>
        <router-link to="/dashboard">总览</router-link>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const showNav = computed(() => route.path !== '/login')
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f7fa; }
.nav-bar { display: flex; align-items: center; padding: 12px 24px; background: #fff; border-bottom: 1px solid #e8e8e8; }
.nav-brand { font-size: 18px; font-weight: 600; color: #1a1a1a; }
.nav-links { margin-left: 40px; display: flex; gap: 24px; }
.nav-links a { text-decoration: none; color: #666; font-size: 14px; padding: 4px 0; }
.nav-links a.router-link-active { color: #1890ff; border-bottom: 2px solid #1890ff; }
.main-content { padding: 24px; max-width: 1400px; margin: 0 auto; }
</style>
