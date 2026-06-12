import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 45000,   // Render free tier can take ~30s to wake up
})

// Wake the backend — call health endpoint silently on startup
export const wakeBackend = () =>
  api.get('/health').catch(() => {})

export const fetchSampleRequirements = () =>
  api.get('/requirements/sample').then(r => r.data)

export const addRequirements = (reqs) =>
  api.post('/requirements/batch', { requirements: reqs }).then(r => r.data)

export const buildGraph = (reqs) =>
  api.post('/graph/build', { requirements: reqs }).then(r => r.data)

export const getCurrentGraph = () =>
  api.get('/graph/current').then(r => r.data)

export const getTraceability = (reqId) =>
  api.get(`/graph/traceability/${reqId}`).then(r => r.data)

export const queryGraph = (query, top_k = 5, use_llm = true) =>
  api.post('/query', { query, top_k, use_llm }).then(r => r.data)

export const verifyAll = () =>
  api.post('/requirements/verify-all').then(r => r.data)

export const verifyOne = (reqId) =>
  api.post(`/requirements/verify/${reqId}`).then(r => r.data)

export const runCypher = (query, params = {}) =>
  api.post('/query/cypher', { query, params }).then(r => r.data)

export const getNeo4jStatus = () =>
  api.get('/graph/neo4j/status').then(r => r.data)

export default api
