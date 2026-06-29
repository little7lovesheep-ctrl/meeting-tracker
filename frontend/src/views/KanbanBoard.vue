<template>
  <div class="kanban-page">
    <div class="kanban-header">
      <div>
        <h2>行动项追踪</h2>
        <p class="kanban-summary">
          {{ focusMode ? '文静重点关注' : '全部已生效事项' }} · 待跟进 {{ store.followUpItems.length }} 项 · 已完成 {{ store.doneItems.length }} 项
        </p>
      </div>
      <div class="kanban-tools">
        <button class="focus-toggle" :class="{ active: focusMode }" @click="toggleFocus">
          {{ focusMode ? '查看全部事项' : '文静重点关注' }}
        </button>
        <select v-model="filterAssignee" @change="fetchData" :disabled="focusMode">
          <option value="">全部成员</option>
          <option v-for="u in users" :key="u.id" :value="u.id">{{ u.name }}</option>
        </select>
      </div>
    </div>

    <div class="kanban-board">
      <div class="kanban-column">
        <div class="column-header todo">待跟进 ({{ store.followUpItems.length }})</div>
        <div class="column-body">
          <div v-for="item in store.followUpItems" :key="item.id" class="kanban-card"
               @click="goDetail(item.id)">
            <div class="card-priority" :class="item.priority"></div>
            <div class="card-content">
              <div class="card-title">{{ item.title }}</div>
              <div class="card-meta">
                <span class="assignee">{{ item.assignee_name || '未分配' }}</span>
                <span v-if="item.watcher_name" class="watcher-chip">关注: {{ item.watcher_name }}</span>
                <span v-if="item.status === 'in_progress'" class="status-chip">已反馈</span>
                <span class="due" :class="{ overdue: isOverdue(item) }">
                  {{ item.due_date || '无截止' }}
                </span>
              </div>
              <div class="focus-reasons" v-if="item.focus_reasons?.length">
                <span v-for="reason in item.focus_reasons" :key="reason">{{ reason }}</span>
              </div>
              <div class="card-actions">
                <button class="btn-mark-done" @click.stop="markDone(item.id)">
                  标记已完成
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="kanban-column">
        <div class="column-header done">已完成 ({{ store.doneItems.length }})</div>
        <div class="column-body">
          <div v-for="item in store.doneItems" :key="item.id" class="kanban-card done-card"
               @click="goDetail(item.id)">
            <div class="card-content">
              <div class="card-title">{{ item.title }}</div>
              <div class="card-meta">
                <span class="assignee">{{ item.assignee_name }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useActionsStore } from '../stores/actions'
import api from '../api'

const store = useActionsStore()
const router = useRouter()
const users = ref([])
const filterAssignee = ref('')
const focusMode = ref(false)

onMounted(async () => {
  await fetchData()
  const { data } = await api.get('/users')
  users.value = data
})

async function fetchData() {
  const params = {}
  if (focusMode.value) {
    params.focus_owner = '文静'
  } else if (filterAssignee.value) {
    params.assignee_id = filterAssignee.value
  }
  await store.fetchAll(params)
}

async function toggleFocus() {
  focusMode.value = !focusMode.value
  if (focusMode.value) filterAssignee.value = ''
  await fetchData()
}

function isOverdue(item) {
  if (!item.due_date) return false
  return new Date(item.due_date) < new Date()
}

function goDetail(id) {
  router.push(`/actions/${id}`)
}

async function markDone(id) {
  await store.updateStatus(id, 'done')
}
</script>
