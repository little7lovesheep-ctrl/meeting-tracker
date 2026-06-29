<template>
  <div class="detail-page" v-if="action">
    <div class="detail-header">
      <router-link to="/kanban" class="back-link">← 返回看板</router-link>
      <h2>{{ action.title }}</h2>
      <div class="detail-meta">
        <span class="assignee">责任人: {{ action.assignee_name || '未分配' }}</span>
        <span v-if="action.watcher_name" class="watcher">关注人: {{ action.watcher_name }}</span>
        <span class="status-tag" :class="action.status">{{ statusLabel }}</span>
        <span class="priority-tag" :class="action.priority">{{ action.priority }}</span>
        <span v-if="action.due_date">截止: {{ action.due_date }}</span>
      </div>
    </div>

    <div class="detail-desc" v-if="action.description">
      <h3>描述</h3>
      <p>{{ action.description }}</p>
    </div>

    <div class="status-actions">
      <button v-if="action.status === 'todo'" @click="changeStatus('in_progress')">开始执行</button>
      <button v-if="action.status === 'in_progress'" @click="changeStatus('done')">标记完成</button>
    </div>

    <div class="checkpoints" v-if="action.checkpoints?.length">
      <h3>Check节点</h3>
      <div v-for="cp in action.checkpoints" :key="cp.id" class="checkpoint-item">
        <span class="cp-icon" :class="{ notified: cp.notified }">●</span>
        <span>{{ cp.description }}</span>
        <span class="cp-date">{{ cp.check_date }}</span>
      </div>
    </div>

    <div class="feedback-section">
      <h3>进度反馈</h3>
      <div class="feedback-form">
        <textarea v-model="feedbackContent" placeholder="填写最新进度..." rows="3"></textarea>
        <div class="progress-input">
          <label>完成度: {{ feedbackProgress }}%</label>
          <input type="range" v-model.number="feedbackProgress" min="0" max="100" />
        </div>
        <button @click="submitFeedback" :disabled="!feedbackContent.trim()">提交反馈</button>
      </div>

      <div class="feedback-timeline">
        <div v-for="fb in feedbacks" :key="fb.id" class="feedback-item">
          <div class="fb-header">
            <span class="fb-user">{{ fb.user_name || '匿名' }}</span>
            <span class="fb-time">{{ formatTime(fb.created_at) }}</span>
            <span class="fb-progress">{{ fb.progress }}%</span>
          </div>
          <div class="fb-content">{{ fb.content }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const action = ref(null)
const feedbacks = ref([])
const feedbackContent = ref('')
const feedbackProgress = ref(0)

const statusLabel = computed(() => {
  const map = { todo: '待办', in_progress: '进行中', done: '已完成' }
  return map[action.value?.status] || ''
})

onMounted(async () => {
  await loadData()
})

async function loadData() {
  const id = route.params.id
  const [actionsRes, fbRes] = await Promise.all([
    api.get('/actions', { params: {} }),
    api.get(`/actions/${id}/feedbacks`),
  ])
  action.value = actionsRes.data.find(a => a.id === parseInt(id))
  feedbacks.value = fbRes.data
}

async function changeStatus(status) {
  await api.put(`/actions/${route.params.id}`, { status })
  action.value.status = status
}

async function submitFeedback() {
  await api.post(`/actions/${route.params.id}/feedback`, {
    content: feedbackContent.value,
    progress: feedbackProgress.value,
  })
  feedbackContent.value = ''
  await loadData()
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}
</script>
