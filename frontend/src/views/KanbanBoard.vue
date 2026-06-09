<template>
  <div class="kanban-page">
    <div class="kanban-header">
      <h2>行动项看板</h2>
      <select v-model="filterAssignee" @change="fetchData">
        <option value="">全部成员</option>
        <option v-for="u in users" :key="u.id" :value="u.id">{{ u.name }}</option>
      </select>
    </div>

    <div class="kanban-board">
      <div class="kanban-column">
        <div class="column-header todo">待办 ({{ store.todoItems.length }})</div>
        <div class="column-body">
          <div v-for="item in store.todoItems" :key="item.id" class="kanban-card"
               @click="goDetail(item.id)">
            <div class="card-priority" :class="item.priority"></div>
            <div class="card-content">
              <div class="card-title">{{ item.title }}</div>
              <div class="card-meta">
                <span class="assignee">{{ item.assignee_name || '未分配' }}</span>
                <span class="due" :class="{ overdue: isOverdue(item) }">
                  {{ item.due_date || '无截止' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="kanban-column">
        <div class="column-header progress">进行中 ({{ store.inProgressItems.length }})</div>
        <div class="column-body">
          <div v-for="item in store.inProgressItems" :key="item.id" class="kanban-card"
               @click="goDetail(item.id)">
            <div class="card-priority" :class="item.priority"></div>
            <div class="card-content">
              <div class="card-title">{{ item.title }}</div>
              <div class="card-meta">
                <span class="assignee">{{ item.assignee_name || '未分配' }}</span>
                <span class="due" :class="{ overdue: isOverdue(item) }">
                  {{ item.due_date || '无截止' }}
                </span>
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

onMounted(async () => {
  await fetchData()
  const { data } = await api.get('/users')
  users.value = data
})

async function fetchData() {
  const params = {}
  if (filterAssignee.value) params.assignee_id = filterAssignee.value
  await store.fetchAll(params)
}

function isOverdue(item) {
  if (!item.due_date) return false
  return new Date(item.due_date) < new Date()
}

function goDetail(id) {
  router.push(`/actions/${id}`)
}
</script>
