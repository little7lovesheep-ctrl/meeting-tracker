<template>
  <div class="meeting-edit-page">
    <div v-if="meeting" class="edit-container">
      <div class="edit-page-header">
        <h2>{{ meeting.title }}</h2>
        <p class="meeting-meta">{{ meeting.meeting_date }} · {{ meeting.channel_name }}</p>
        <p class="edit-tip" v-if="meeting.status === 'draft'">请确认你的行动项，修改后点击「确认修改」保存</p>
        <p class="edit-tip active-tip" v-else>该会议已生效，行动项正在跟进中</p>
      </div>

      <!-- 责任人筛选 -->
      <div class="filter-bar">
        <span class="filter-label">筛选：</span>
        <button
          class="filter-btn"
          :class="{ active: filterName === '' }"
          @click="filterName = ''"
        >全部 ({{ items.length }})</button>
        <button
          v-for="name in assigneeList"
          :key="name"
          class="filter-btn"
          :class="{ active: filterName === name }"
          @click="filterName = name"
        >{{ name }} ({{ countByAssignee(name) }})</button>
      </div>

      <div class="edit-items-list">
        <div v-for="item in filteredItems" :key="item.id" class="member-edit-card" :class="{ 'card-modified': item._modified }">
          <div class="member-card-header">
            <span class="assignee-badge">{{ item.assignee_name || '未分配' }}</span>
            <span class="watcher-badge" v-if="item.watcher_name">关注: {{ item.watcher_name }}</span>
            <span class="priority-tag" :class="item.priority">{{ priorityLabel(item.priority) }}</span>
            <span class="save-status saved" v-if="item._saved">已保存 ✓</span>
            <span class="save-status modified" v-else-if="item._modified">有修改未保存</span>
          </div>
          <div class="member-field">
            <label>行动项</label>
            <input v-model="item.title" @input="item._modified = true" :disabled="meeting.status === 'active'" />
          </div>
          <div class="member-row">
            <div class="member-field flex-1">
              <label>责任人</label>
              <select v-model="item.assignee_name" @change="item._modified = true">
                <option value="">未分配</option>
                <option v-for="u in users" :key="u.id" :value="u.name">{{ u.name }}</option>
              </select>
            </div>
            <div class="member-field flex-1">
              <label>关注人 / Check人</label>
              <select v-model="item.watcher_name" @change="item._modified = true">
                <option value="">不指定</option>
                <option v-for="u in users" :key="u.id" :value="u.name">{{ u.name }}</option>
              </select>
            </div>
            <div class="member-field flex-1">
              <label>截止日期</label>
              <input type="date" v-model="item.due_date" @input="item._modified = true" />
            </div>
            <div class="member-field flex-1">
              <label>优先级</label>
              <select v-model="item.priority" @change="item._modified = true">
                <option value="high">高</option>
                <option value="medium">中</option>
                <option value="low">低</option>
              </select>
            </div>
          </div>
          <div class="member-field">
            <label>描述 / 备注</label>
            <input v-model="item.description" @input="item._modified = true" placeholder="补充说明" />
          </div>
          <div class="checkpoints-edit">
            <label>Check节点</label>
            <div v-for="(cp, cpIdx) in item.checkpoints" :key="cpIdx" class="cp-row">
              <input type="date" v-model="cp.check_date" class="cp-date" @input="item._modified = true" />
              <input v-model="cp.description" class="cp-desc" placeholder="检查内容" @input="item._modified = true" />
              <button class="btn-cp-delete" @click="removeCp(item, cpIdx)">×</button>
            </div>
            <button class="btn-add-cp" @click="addCp(item)">+ 添加check点</button>
          </div>
          <div class="card-actions">
            <span class="confirmed-badge" v-if="item.confirmed && !item._modified">已确认 ✓</span>
            <template v-else>
              <button class="btn-confirm-ok" @click="confirmItem(item)" v-if="!item._modified" :disabled="item._saving">
                确认无异议
              </button>
              <button class="btn-confirm-save" @click="saveItem(item)" v-if="item._modified" :disabled="item._saving">
                {{ item._saving ? '保存中...' : '保存修改' }}
              </button>
            </template>
          </div>
        </div>
      </div>
    </div>
    <div v-else-if="loadError" class="error-state">
      <p>{{ loadError }}</p>
      <button class="btn-primary" @click="loadMeeting">重试</button>
    </div>
    <div v-else class="loading-state">加载中...</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const meeting = ref(null)
const items = ref([])
const users = ref([])
const filterName = ref('')
const loadError = ref('')

onMounted(async () => {
  await loadMeeting()
})

async function loadMeeting() {
  loadError.value = ''
  try {
    const { data } = await api.get(`/meetings/${route.params.id}/edit`)
    const usersRes = await api.get('/users')
    meeting.value = data
    users.value = usersRes.data
    items.value = data.action_items.map(item => ({
      ...item,
      checkpoints: item.checkpoints || [],
      _saved: false,
      _modified: false,
      _saving: false,
    }))
  } catch (e) {
    loadError.value = e.response?.data?.detail || '加载失败，请检查链接是否正确'
  }
}

const assigneeList = computed(() => {
  const names = [...new Set(items.value.map(i => i.assignee_name).filter(Boolean))]
  return names
})

const filteredItems = computed(() => {
  if (!filterName.value) return items.value
  return items.value.filter(i => i.assignee_name === filterName.value)
})

function countByAssignee(name) {
  return items.value.filter(i => i.assignee_name === name).length
}

function priorityLabel(p) {
  return { high: '高优', medium: '中优', low: '低优' }[p] || '中优'
}

async function saveItem(item) {
  item._saving = true
  try {
    await api.put(`/meetings/${route.params.id}/items/${item.id}`, {
      title: item.title,
      description: item.description,
      assignee_name: item.assignee_name,
      watcher_name: item.watcher_name,
      priority: item.priority,
      due_date: item.due_date,
      checkpoints: item.checkpoints.filter(cp => cp.check_date),
    })
    item._saved = true
    item._modified = false
    item.confirmed = true
    setTimeout(() => { item._saved = false }, 3000)
  } catch (e) {
    alert('保存失败，请重试')
  } finally {
    item._saving = false
  }
}

async function confirmItem(item) {
  item._saving = true
  try {
    await api.put(`/meetings/${route.params.id}/items/${item.id}/confirm`)
    item.confirmed = true
  } catch (e) {
    alert('确认失败，请重试')
  } finally {
    item._saving = false
  }
}

function addCp(item) {
  item.checkpoints.push({ check_date: '', description: '' })
  item._modified = true
}

function removeCp(item, idx) {
  item.checkpoints.splice(idx, 1)
  item._modified = true
}
</script>
