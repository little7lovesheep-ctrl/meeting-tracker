import { defineStore } from 'pinia'
import api from '../api'

export const useActionsStore = defineStore('actions', {
  state: () => ({
    items: [],
    loading: false,
  }),
  getters: {
    followUpItems: (state) => state.items.filter(i => i.status !== 'done'),
    todoItems: (state) => state.items.filter(i => i.status === 'todo'),
    inProgressItems: (state) => state.items.filter(i => i.status === 'in_progress'),
    doneItems: (state) => state.items.filter(i => i.status === 'done'),
  },
  actions: {
    async fetchAll(params = {}) {
      this.loading = true
      try {
        const { data } = await api.get('/actions', { params })
        this.items = data
      } finally {
        this.loading = false
      }
    },
    async updateStatus(id, status) {
      await api.put(`/actions/${id}`, { status })
      const item = this.items.find(i => i.id === id)
      if (item) item.status = status
    },
  },
})
