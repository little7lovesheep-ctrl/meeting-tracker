<template>
  <div class="import-page">
    <h2>导入会议纪要</h2>

    <!-- 步骤1：输入 -->
    <div class="import-form" v-if="step === 'input'">
      <div class="form-group">
        <label>会议日期</label>
        <input type="date" v-model="meetingDate" />
      </div>
      <div class="form-group">
        <label>推送到哪个群</label>
        <select v-model="channelName" required>
          <option value="" disabled>请选择推送群</option>
          <option v-for="ch in channels" :key="ch.id" :value="ch.name">{{ ch.name }}</option>
        </select>
      </div>
      <div class="form-group">
        <label>会议纪要内容</label>
        <div class="input-tabs">
          <button class="tab-btn" :class="{ active: inputMode === 'paste' }" @click="inputMode = 'paste'">粘贴文本</button>
          <button class="tab-btn" :class="{ active: inputMode === 'file' }" @click="inputMode = 'file'">上传文件</button>
        </div>
        <textarea v-if="inputMode === 'paste'" v-model="rawText" placeholder="粘贴会议纪要文本..." rows="12"></textarea>
        <div v-else class="file-upload-area">
          <input type="file" ref="fileInput" @change="handleFileUpload" accept=".txt,.md,.doc,.docx,.pdf" class="file-input" />
          <div class="upload-placeholder" v-if="!fileName"
               @click="$refs.fileInput.click()"
               @dragover.prevent="dragOver = true"
               @dragleave="dragOver = false"
               @drop.prevent="handleDrop"
               :class="{ 'drag-active': dragOver }">
            点击选择文件或拖拽到此处<br/>
            <span class="upload-hint">支持 .txt .md .docx .pdf 格式</span>
          </div>
          <div class="upload-done" v-else>
            <span class="file-name">{{ fileName }}</span>
            <button class="btn-remove-file" @click="clearFile">移除</button>
          </div>
          <div v-if="rawText && inputMode === 'file'" class="file-preview">
            <label>文件内容预览（前500字）</label>
            <pre>{{ rawText.slice(0, 500) }}{{ rawText.length > 500 ? '...' : '' }}</pre>
          </div>
        </div>
      </div>
      <button class="btn-primary" @click="parseNotes" :disabled="loading || !rawText.trim() || !channelName">
        {{ loading ? 'AI解析中...' : 'AI智能解析' }}
      </button>
      <div v-if="loading" class="loading-tip">
        <span class="loading-spinner"></span>
        正在解析会议纪要，预计需要1分钟左右，请耐心等待...
        <span class="loading-timer" v-if="loadingSeconds > 0">已等待 {{ loadingSeconds }}s</span>
      </div>
      <div v-if="error" class="error-msg">{{ error }}</div>
      <div v-if="inputMode === 'file' && fileName && !rawText" class="error-msg">文件内容读取中，请稍候...</div>
    </div>

    <!-- 步骤2：预览编辑 -->
    <div v-if="step === 'edit'" class="edit-section">
      <div class="edit-header">
        <div class="form-group">
          <label>会议标题</label>
          <input v-model="editTitle" />
        </div>
        <p class="result-count">共 {{ editItems.length }} 个行动项 → 将推送到「{{ channelName }}」供团队确认</p>
        <button class="btn-secondary btn-small" @click="setAllWatcher('文静')">全部设为文静关注</button>
      </div>

      <div class="edit-actions-list">
        <div v-for="(item, idx) in editItems" :key="idx" class="edit-card">
          <div class="edit-card-header">
            <span class="edit-index">#{{ idx + 1 }}</span>
            <button class="btn-delete" @click="removeItem(idx)">删除</button>
          </div>
          <div class="edit-row">
            <div class="edit-field flex-2">
              <label>行动项</label>
              <input v-model="item.title" />
            </div>
            <div class="edit-field flex-1">
              <label>责任人</label>
              <select v-model="item.assignee_name">
                <option value="">未分配</option>
                <option v-for="u in users" :key="u.id" :value="u.name">{{ u.name }}</option>
              </select>
            </div>
            <div class="edit-field flex-1">
              <label>关注人 / Check人</label>
              <select v-model="item.watcher_name">
                <option value="">不指定</option>
                <option v-for="u in users" :key="u.id" :value="u.name">{{ u.name }}</option>
              </select>
            </div>
          </div>
          <div class="edit-row">
            <div class="edit-field flex-1">
              <label>优先级</label>
              <select v-model="item.priority">
                <option value="high">高</option>
                <option value="medium">中</option>
                <option value="low">低</option>
              </select>
            </div>
            <div class="edit-field flex-1">
              <label>截止日期</label>
              <input type="date" v-model="item.due_date" />
            </div>
          </div>
          <div class="edit-field">
            <label>描述</label>
            <input v-model="item.description" placeholder="可选" />
          </div>
          <div class="checkpoints-edit">
            <label>Check节点</label>
            <div v-for="(cp, cpIdx) in item.checkpoints" :key="cpIdx" class="cp-row">
              <input type="date" v-model="cp.check_date" class="cp-date" />
              <input v-model="cp.description" class="cp-desc" placeholder="检查内容" />
              <button class="btn-cp-delete" @click="item.checkpoints.splice(cpIdx, 1)">×</button>
            </div>
            <button class="btn-add-cp" @click="item.checkpoints.push({ check_date: '', description: '' })">+ 添加check点</button>
          </div>
        </div>
      </div>

      <button class="btn-add-item" @click="addItem">+ 新增行动项</button>

      <div class="edit-footer">
        <button class="btn-secondary" @click="step = 'input'">返回修改纪要</button>
        <button class="btn-primary" @click="publishDraft" :disabled="saving">
          {{ saving ? '推送中...' : '推送到群并等待确认' }}
        </button>
      </div>
    </div>

    <!-- 步骤3：已推送 -->
    <div v-if="step === 'sent'" class="done-section">
      <div class="done-icon">✓</div>
      <h3>已推送到「{{ channelName }}」</h3>
      <p>团队成员可通过群里的链接修改自己的行动项</p>
      <p class="form-hint">等大家确认后，你可以去审核页确认生效</p>
      <div class="done-buttons">
        <button class="btn-secondary" @click="resetAll">继续导入</button>
        <router-link :to="`/meetings/${draftMeetingId}/review`" class="btn-primary">去审核确认</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const step = ref('input')
const rawText = ref('')
const meetingDate = ref(new Date().toISOString().split('T')[0])
const channelName = ref('')
const channels = ref([])
const users = ref([])
const loading = ref(false)
const loadingSeconds = ref(0)
let loadingTimer = null
const saving = ref(false)
const error = ref('')
const inputMode = ref('paste')
const fileName = ref('')
const fileInput = ref(null)
const dragOver = ref(false)

const editTitle = ref('')
const editItems = ref([])
const draftMeetingId = ref(null)

onMounted(async () => {
  const [chRes, uRes] = await Promise.all([
    api.get('/channels'),
    api.get('/users'),
  ])
  channels.value = chRes.data
  users.value = uRes.data
})

function handleDrop(e) {
  dragOver.value = false
  const file = e.dataTransfer.files[0]
  if (!file) return
  processFile(file)
}

async function handleFileUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  processFile(file)
}

async function processFile(file) {
  fileName.value = file.name
  error.value = ''

  const ext = file.name.split('.').pop().toLowerCase()

  if (['txt', 'md'].includes(ext)) {
    rawText.value = await file.text()
  } else if (['doc', 'docx', 'pdf'].includes(ext)) {
    const formData = new FormData()
    formData.append('file', file)
    try {
      const { data } = await api.post('/meetings/upload-file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      rawText.value = data.text
    } catch (err) {
      error.value = '文件解析失败：' + (err.response?.data?.detail || '请重试')
      fileName.value = ''
    }
  } else {
    error.value = '不支持的文件格式，请使用 .txt .md .docx .pdf'
    fileName.value = ''
  }
}

function clearFile() {
  fileName.value = ''
  rawText.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

async function parseNotes() {
  loading.value = true
  loadingSeconds.value = 0
  loadingTimer = setInterval(() => { loadingSeconds.value++ }, 1000)
  error.value = ''
  try {
    const { data } = await api.post('/meetings/parse', {
      raw_text: rawText.value,
      meeting_date: meetingDate.value,
    })
    editTitle.value = data.meeting_title || `会议 ${meetingDate.value}`
    editItems.value = (data.action_items || []).map(item => ({
      title: item.title || '',
      description: item.description || '',
      assignee_name: item.assignee_name || '',
      watcher_name: item.watcher_name || '',
      priority: item.priority || 'medium',
      due_date: item.due_date || '',
      checkpoints: (item.checkpoints || []).map(cp => ({
        check_date: cp.check_date || '',
        description: cp.description || '',
      })),
    }))
    step.value = 'edit'
  } catch (e) {
    error.value = e.response?.data?.detail || '解析失败，请重试'
  } finally {
    loading.value = false
    clearInterval(loadingTimer)
    loadingSeconds.value = 0
  }
}

function removeItem(idx) { editItems.value.splice(idx, 1) }
function addItem() {
  editItems.value.push({ title: '', description: '', assignee_name: '', watcher_name: '', priority: 'medium', due_date: '', checkpoints: [] })
}

function setAllWatcher(name) {
  editItems.value.forEach(item => { item.watcher_name = name })
}

async function publishDraft() {
  saving.value = true
  error.value = ''
  try {
    const { data } = await api.post('/meetings/draft', {
      raw_text: rawText.value,
      meeting_date: meetingDate.value,
      title: editTitle.value,
      channel_name: channelName.value,
      action_items: editItems.value.filter(i => i.title.trim()),
    })
    draftMeetingId.value = data.meeting_id
    step.value = 'sent'
  } catch (e) {
    error.value = e.response?.data?.detail || '推送失败'
  } finally {
    saving.value = false
  }
}

function resetAll() {
  step.value = 'input'
  rawText.value = ''
  editTitle.value = ''
  editItems.value = []
  draftMeetingId.value = null
  error.value = ''
}
</script>
