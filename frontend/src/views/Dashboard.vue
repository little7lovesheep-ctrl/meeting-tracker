<template>
  <div class="dashboard-page">
    <h2>全局总览</h2>

    <div class="stats-grid" v-if="stats">
      <div class="stat-card">
        <div class="stat-number">{{ stats.total }}</div>
        <div class="stat-label">总行动项</div>
      </div>
      <div class="stat-card">
        <div class="stat-number progress-color">{{ stats.in_progress }}</div>
        <div class="stat-label">进行中</div>
      </div>
      <div class="stat-card">
        <div class="stat-number done-color">{{ stats.done }}</div>
        <div class="stat-label">已完成</div>
      </div>
      <div class="stat-card">
        <div class="stat-number overdue-color">{{ stats.overdue }}</div>
        <div class="stat-label">已逾期</div>
      </div>
    </div>

    <div class="section">
      <h3>各成员负载</h3>
      <div class="assignee-list">
        <div v-for="a in stats?.by_assignee" :key="a.assignee_name" class="assignee-row">
          <span class="name">{{ a.assignee_name }}</span>
          <div class="bar-wrapper">
            <div class="bar-done" :style="{ width: (a.done_count / a.count * 100) + '%' }"></div>
          </div>
          <span class="count">{{ a.done_count }}/{{ a.count }}</span>
        </div>
      </div>
    </div>

    <div class="section" v-if="overdueItems.length">
      <h3>逾期行动项</h3>
      <div class="overdue-list">
        <div v-for="item in overdueItems" :key="item.id" class="overdue-item"
             @click="$router.push(`/actions/${item.id}`)">
          <span class="title">{{ item.title }}</span>
          <span class="assignee">{{ item.assignee_name || '未分配' }}</span>
          <span class="due">截止: {{ item.due_date }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const stats = ref(null)
const overdueItems = ref([])

onMounted(async () => {
  const [dashRes, overdueRes] = await Promise.all([
    api.get('/actions/dashboard'),
    api.get('/actions/overdue'),
  ])
  stats.value = dashRes.data
  overdueItems.value = overdueRes.data
})
</script>
