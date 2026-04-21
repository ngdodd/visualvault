import axios from 'axios'

const API_BASE = '/api/v1'

// Create axios instance
const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const auth = {
  async register(email, password) {
    const response = await api.post('/auth/register', { email, password })
    return response.data
  },

  async login(email, password) {
    const response = await api.post('/auth/login', { email, password })
    return response.data
  },

  async getMe() {
    const response = await api.get('/auth/me')
    return response.data
  },

  logout() {
    localStorage.removeItem('token')
  },
}

// Assets API
export const assets = {
  async list(page = 1, pageSize = 20, status = null) {
    const params = { page, page_size: pageSize }
    if (status) params.status = status
    const response = await api.get('/assets', { params })
    return response.data
  },

  async get(id) {
    const response = await api.get(`/assets/${id}`)
    return response.data
  },

  async upload(file, onProgress) {
    const formData = new FormData()
    formData.append('file', file)

    const response = await api.post('/assets/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percent)
        }
      },
    })
    return response.data
  },

  async delete(id) {
    await api.delete(`/assets/${id}`)
  },

  getFileUrl(id) {
    const token = localStorage.getItem('token')
    return `${API_BASE}/assets/${id}/file?token=${token}`
  },

  getSegmentUrl(id, numClusters = 5) {
    const token = localStorage.getItem('token')
    return `${API_BASE}/assets/${id}/segment?num_clusters=${numClusters}&token=${token}`
  },

  async getSegmentInfo(id, numClusters = 5) {
    const response = await api.get(`/assets/${id}/segment/info`, {
      params: { num_clusters: numClusters },
    })
    return response.data
  },
}

// Search API
export const search = {
  async byText(query, limit = 20, minSimilarity = 0.1) {
    const response = await api.post('/search/text', {
      query,
      limit,
      min_similarity: minSimilarity,
    })
    return response.data
  },

  async byLabel(label, limit = 50) {
    const response = await api.get('/search/labels', {
      params: { label, limit },
    })
    return response.data
  },

  async similar(assetId, limit = 20, minSimilarity = 0.5) {
    const response = await api.post(`/search/similar/${assetId}`, null, {
      params: { limit, min_similarity: minSimilarity },
    })
    return response.data
  },

  async getAvailableLabels() {
    const response = await api.get('/search/labels/available')
    return response.data
  },
}

// Analysis API (Object Detection, etc.)
export const analysis = {
  async getModels() {
    const response = await api.get('/analysis/models')
    return response.data
  },

  async detect(assetId, options = {}) {
    const { model = 'yolov8n', confidence = 0.25, maxDetections = 50 } = options
    const response = await api.get(`/analysis/detect/${assetId}`, {
      params: { model, confidence, max_detections: maxDetections },
    })
    return response.data
  },

  getVisualizeUrl(assetId, options = {}) {
    const { model = 'yolov8n', confidence = 0.25, showLabels = true, showConfidence = true } = options
    const token = localStorage.getItem('token')
    const params = new URLSearchParams({
      model,
      confidence,
      show_labels: showLabels,
      show_confidence: showConfidence,
      token,
    })
    return `${API_BASE}/analysis/detect/${assetId}/visualize?${params}`
  },

  async getMetrics(model = null) {
    const response = await api.get('/analysis/metrics', {
      params: model ? { model } : {},
    })
    return response.data
  },

  async compare(assetId, models = ['yolov8n', 'yolov8s'], confidence = 0.25) {
    const response = await api.get('/analysis/compare', {
      params: { asset_id: assetId, models: models.join(','), confidence },
    })
    return response.data
  },

  // Style Transfer
  async getStyles() {
    const response = await api.get('/analysis/styles')
    return response.data
  },

  getStyledImageUrl(assetId, preset, alpha = 1.0) {
    const token = localStorage.getItem('token')
    const params = new URLSearchParams({
      preset,
      alpha,
      token,
    })
    return `${API_BASE}/analysis/style/${assetId}?${params}`
  },

  async customStyleTransfer(contentAssetId, styleFile, alpha = 1.0, onProgress) {
    const formData = new FormData()
    formData.append('style_file', styleFile)

    const response = await api.post(
      `/analysis/style/${contentAssetId}/with-image`,
      formData,
      {
        params: { alpha },
        headers: { 'Content-Type': 'multipart/form-data' },
        responseType: 'blob',
        onUploadProgress: (progressEvent) => {
          if (onProgress) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            onProgress(percent)
          }
        },
      }
    )
    // Convert blob to base64
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onloadend = () => {
        resolve({
          styled_image_base64: reader.result.split(',')[1],
        })
      }
      reader.onerror = reject
      reader.readAsDataURL(response.data)
    })
  },
}

// Tags API
export const tags = {
  async list(sortBy = 'usage') {
    const response = await api.get('/tags', { params: { sort_by: sortBy } })
    return response.data
  },

  async create(name) {
    const response = await api.post('/tags', { name })
    return response.data
  },

  async delete(tagId) {
    await api.delete(`/tags/${tagId}`)
  },

  async getAssetTags(assetId) {
    const response = await api.get(`/tags/assets/${assetId}`)
    return response.data
  },

  async updateAssetTags(assetId, tagList) {
    const response = await api.put(`/tags/assets/${assetId}`, { tags: tagList })
    return response.data
  },

  async addTagToAsset(assetId, tagName) {
    const response = await api.post(`/tags/assets/${assetId}/add`, { name: tagName })
    return response.data
  },

  async removeTagFromAsset(assetId, tagName) {
    const response = await api.delete(`/tags/assets/${assetId}/remove/${encodeURIComponent(tagName)}`)
    return response.data
  },
}

// Health API
export const health = {
  async check() {
    const response = await api.get('/health')
    return response.data
  },

  async detailed() {
    const response = await api.get('/health/detailed')
    return response.data
  },
}

export default api
