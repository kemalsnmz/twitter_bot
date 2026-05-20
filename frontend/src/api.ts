import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN = import.meta.env.VITE_AUTH_TOKEN || ''

const client = axios.create({
  baseURL: BASE,
  headers: { 'X-Auth-Token': TOKEN },
})

export const api = {
  stats: () => client.get('/api/stats').then(r => r.data),
  pending: () => client.get('/api/pending').then(r => r.data),
  approve: (id: number) => client.post(`/api/tweets/${id}/approve`).then(r => r.data),
  reject: (id: number) => client.post(`/api/tweets/${id}/reject`).then(r => r.data),
  edit: (id: number, text: string) => client.post(`/api/tweets/${id}/edit`, { text }).then(r => r.data),
  archive: (page = 1) => client.get(`/api/archive?page=${page}`).then(r => r.data),
  recent: () => client.get('/api/recent').then(r => r.data),
  runPipeline: () => client.post('/api/pipeline/run').then(r => r.data),
  imageUrl: (contentId: number) => `${BASE}/api/image/${contentId}?token=${TOKEN}`,
}
