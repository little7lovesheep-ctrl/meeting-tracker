<template>
  <div class="review-page">
    <div v-if="meeting">
      <div class="review-header">
        <router-link to="/kanban" class="back-link">← 返回看板</router-link>
        <h2>{{ meeting.title }}</h2>
        <div class="review-meta">
          <span>{{ meeting.meeting_date }}</span>
          <span>推送到: {{ meeting.channel_name }}</span>
          <span class="status-badge" :class="meeting.status">{{ meeting.status === 'draft' ? '待确认' : '已生效' }}</span>
        </div>
      </div>

      <div class="review-items">
        <div v-for="item in items" :key="item.id" class="review-card">
          <div class="review-card-header">
            <span class="assignee-badge">{{ item.assignee_name || '未分配' }}</span>
            <span class="priority-tag" :class="item.priority">{{ priorityLabel(item.priority) }}</span>
          </div>
          <div class="review-title">{{ item.title }}</div>
          <div class="review-desc" v-if="item.description">{{ item.description }}</div>
          <div class="review-detail">
            <span>截止: {{ item.due_date || '未设定' }}</span>
            <span v-if="item.checkpoints?.length">{{ item.checkpoints.length }} 个check点</span>
          </div>
          <div class="review-checkpoints" v-if="item.checkpoints?.length">
            <div v-for="cp in item.checkpoints" :key="cp.id" class="review-cp">
              <span class="cp-dot">●</span>
              <span class="cp-date">{{ cp.check_date }}</span>
              <span>{{ cp.description }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="review-footer" v-if="meeting.status === 'draft'">
        <p class="review-hint">确认后行动项正式生效，系统将按check节点定时推送提醒</p>
        <button class="btn-primary btn-large" @click="activate" :disabled="activating">
          {{ activating ? '确认中...' : '确认生效，开始跟进' }}
        </button>
      </div>

      <div class="review-footer active-footer" v-else>
        <p class="review-hint">该会议行动项已生效，正在跟进中</p>
        <router-link to="/kanban" class="btn-primary">查看看板</router-link>
      </div>
    </div>
    <div v-else class="loading-state">加载中...</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const meeting = ref(null)
const items = ref([])
const activating = ref(false)

onMounted(async () => { await loadData() })

async function loadData() {
  const { data } = await api.get(`/meetings/${route.params.id}/edit`)
  meeting.value = data
  items.value = data.action_items || []
}

function priorityLabel(p) {
  return { high: '高优', medium: '中优', low: '低优' }[p] || '中优'
}

async function activate() {
  activating.value = true
  try {
    await api.put(`/meetings/${route.params.id}/activate`)
    meeting.value.status = 'active'
  } catch (e) {
    alert(e.response?.data?.detail || '操作失败')
  } finally {
    activating.value = false
  }
}
</script>
