<template>
  <div class="report-panel">
    <div class="panel-header">
      <div class="header-info">
        <h3>Report</h3>
        <p class="subtitle">Final research synthesis</p>
      </div>
      <div class="header-actions">
        <button @click="refresh" :disabled="loading" class="refresh-btn">
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div v-if="report?.status !== 'ready'" class="placeholder">
      <p v-if="report?.status === 'pending'">The final report will appear here when the research session completes.</p>
      <p v-else-if="report?.status">{{ report.status }}</p>
      <p v-else>No report available yet.</p>
    </div>

    <div v-else class="report-body">
      <div v-if="outline.length" class="outline-section">
        <button class="outline-toggle" @click="showOutline = !showOutline">
          <span>Key Hypotheses ({{ outline.length }})</span>
          <span>{{ showOutline ? 'Collapse' : 'Expand' }}</span>
        </button>
        <div v-if="showOutline" class="outline">
          <div v-for="(section, index) in outline" :key="section.id || index" class="outline-item">
            <span class="num">{{ index + 1 }}</span>
            <span class="title">{{ section.text || section.title }}</span>
          </div>
        </div>
      </div>

      <div v-if="report?.markdown" class="report-content">
        <pre class="report-text">{{ report.markdown }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({ sessionId: { type: String, required: true } })

const report = ref(null)
const outline = ref([])
const loading = ref(false)
const showOutline = ref(true)

async function refresh() {
  loading.value = true
  try {
    const result = await api.getReport(props.sessionId)
    report.value = result
    outline.value = result?.meta?.top_hypotheses || []
  } catch (error) {
    report.value = { status: 'error', error: error.message }
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
watch(() => props.sessionId, refresh)
</script>

<style scoped>
.report-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fff;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
  gap: 16px;
}

.header-info h3 {
  margin: 0 0 4px;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.subtitle {
  margin: 0;
  font-size: 11px;
  color: #666;
}

.refresh-btn {
  padding: 6px 12px;
  border: 1px solid #111;
  background: #fff;
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.refresh-btn:hover {
  background: #f5f5f5;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #666;
  font-size: 12px;
}

.report-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.outline-section {
  border-bottom: 1px solid #eee;
  flex: 0 0 auto;
}

.outline-toggle {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: none;
  background: #fafafa;
  padding: 10px 16px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
}

.outline-toggle:hover {
  background: #f0f0f0;
}

.outline {
  padding: 10px 16px;
  background: #fff;
}

.outline-item {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
}

.num {
  color: #999;
  width: 20px;
  flex-shrink: 0;
}

.title {
  color: #333;
}

.report-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px;
}

.report-text {
  background: #fafafa;
  border: 1px solid #eee;
  padding: 16px;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
}
</style>
