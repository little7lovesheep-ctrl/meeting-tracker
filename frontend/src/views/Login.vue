<template>
  <div class="login-page">
    <div class="login-card">
      <h2>货车宝会议关键事项追踪</h2>
      <p>会议讨论事项跟进系统</p>
      <div class="form-group">
        <input v-model="name" placeholder="姓名" @keyup.enter="login" />
      </div>
      <div class="form-group">
        <input v-model="password" type="password" placeholder="密码" @keyup.enter="login" />
      </div>
      <button @click="login" :disabled="!name">登录</button>
      <p class="error" v-if="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const router = useRouter()
const name = ref('')
const password = ref('')
const error = ref('')

async function login() {
  try {
    const { data } = await api.post('/auth/login', { name: name.value, password: password.value })
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify(data.user))
    router.push('/kanban')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败'
  }
}
</script>
