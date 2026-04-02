<template>
  <div class="experiment-tab">
    <div class="panel-header">
      <h3>Experiment Inspector</h3>
      <p class="intro">Select an experiment in the graph or experiments board to view details.</p>
    </div>

    <div v-if="!experimentId" class="empty-state">
      <p>Click an experiment node in the graph or select a card in Experiments mode.</p>
    </div>

    <div v-else-if="loading" class="loading-state">
      <p>Loading experiment...</p>
    </div>

    <div v-else-if="experiment" class="experiment-content">
      <section class="section hero">
        <div class="hero-top">
          <div>
            <div class="experiment-title">{{ experiment.name || experiment.spec_expected_outcome || 'Untitled Experiment' }}</div>
            <div class="experiment-meta">{{ experiment.id }}</div>
          </div>
          <span class="status-badge" :class="experiment.status || 'pending'">
            {{ experiment.status || 'pending' }}
          </span>
        </div>
      </section>

      <section v-if="experiment.spec_expected_outcome" class="section">
        <h4>Expected Outcome</h4>
        <div class="outcome">{{ experiment.spec_expected_outcome }}</div>
      </section>

      <section v-if="experiment.spec_code" class="section">
        <h4>Code / Method</h4>
        <pre class="code-block">{{ experiment.spec_code }}</pre>
      </section>

      <section v-if="experiment.actual_outcome" class="section">
        <h4>Actual Outcome</h4>
        <div class="outcome">{{ experiment.actual_outcome }}</div>
      </section>

      <section v-if="experiment.results" class="section">
        <h4>Results</h4>
        <pre class="code-block">{{ formatResults(experiment.results) }}</pre>
      </section>

      <section class="section">
        <h4>Metadata</h4>
        <div class="meta-grid">
          <div v-if="experiment.created_by"><span>Agent</span>{{ experiment.created_by }}</div>
          <div v-if="experiment.started_at"><span>Started</span>{{ formatTime(experiment.started_at) }}</div>
          <div v-if="experiment.completed_at"><span>Completed</span>{{ formatTime(experiment.completed_at) }}</div>
          <div v-if="experiment.duration"><span>Duration</span>{{ experiment.duration }}</div>
          <div v-if="experiment.priority"><span>Priority</span>{{ experiment.priority }}</div>
          <div v-if="experiment.retries"><span>Retries</span>{{ experiment.retries }}</div>
        </div>
      </section>

      <section v-if="experiment.error_message" class="section error-section">
        <h4>Error</h4>
        <div class="error-message">{{ experiment.error_message }}</div>
      </section>

      <section v-if="experiment.tags?.length" class="section">
        <h4>Tags</h4>
        <div class="tag-list">
          <span v-for="tag in experiment.tags" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </section>

      <section v-if="experiment.related_findings?.length" class="section">
        <h4>Related Findings</h4>
        <div class="compact-list">
          <div v-for="finding in experiment.related_findings" :key="finding.id" class="compact-card">
            <div class="compact-title">{{ truncate(finding.statement || finding.title, 80) }}</div>
            <div class="compact-meta">{{ finding.id }}</div>
          </div>
        </div>
      </section>
    </div>

    <div v-else class="empty-state">
      <p>Experiment not found or not yet available.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api } from '../../api/index.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  experimentId: { type: String, default: '' },
})

const experiment = ref(null)
const loading = ref(false)

watch(
  () => props.experimentId,
  async (value) => {
    if (!value) {
      experiment.value = null
      return
    }
    loading.value = true
    try {
      const result = await api.getExperiment(props.sessionId, value)
      experiment.value = result.experiment || result
    } catch (error) {
      experiment.value = null
    } finally {
      loading.value = false
    }
  },
  { immediate: true }
)

function formatTime(timestamp) {
  if (!timestamp) return '--'
  return new Date(timestamp).toLocaleString()
}

function formatResults(results) {
  if (typeof results === 'string') return results
  return JSON.stringify(results, null, 2)
}

function truncate(value, length) {
  const text = String(value || '')
  return text.length > length ? `${text.slice(0, length - 3)}...` : text
}
</script>

<style scoped>
.experiment-tab {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.panel-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

h3 {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 0;
}

.intro {
  margin: 0;
  font-size: 11px;
  color: #666;
  line-height: 1.4;
}

.empty-state,
.loading-state {
  border: 1px dashed #ddd;
  padding: 14px;
  font-size: 11px;
  color: #666;
  text-align: center;
}

.experiment-content {
  min-width: 0;
}

.section {
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f0f0f0;
  min-width: 0;
}

.hero-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.experiment-title {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
}

.experiment-meta {
  font-family: monospace;
  font-size: 10px;
  color: #777;
  margin-top: 4px;
}

.status-badge {
  font-size: 10px;
  padding: 2px 6px;
  text-transform: uppercase;
  border: 1px solid currentColor;
}

.status-badge.completed {
  color: #2f7d3b;
}

.status-badge.running {
  color: #1565c0;
}

.status-badge.pending,
.status-badge.queued {
  color: #6d4c41;
}

.status-badge.failed {
  color: #bf3a3a;
}

h4 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #666;
  margin: 0 0 8px;
}

.outcome {
  font-size: 12px;
  line-height: 1.5;
  color: #333;
}

.code-block {
  margin: 0;
  padding: 10px;
  border: 1px solid #eee;
  background: #fafafa;
  font-size: 10px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow: auto;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  font-size: 11px;
}

.meta-grid span {
  display: block;
  font-size: 10px;
  text-transform: uppercase;
  color: #777;
  margin-bottom: 3px;
}

.error-section {
  background: #fff5f5;
  margin-left: -12px;
  margin-right: -12px;
  padding-left: 12px;
  padding-right: 12px;
}

.error-message {
  font-size: 11px;
  color: #bf3a3a;
  font-family: monospace;
  line-height: 1.45;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  padding: 2px 6px;
  border: 1px solid #ddd;
  font-size: 10px;
  text-transform: uppercase;
}

.compact-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.compact-card {
  border: 1px solid #eee;
  background: #fafafa;
  padding: 8px;
}

.compact-title {
  font-size: 11px;
  font-weight: 600;
  color: #111;
  line-height: 1.35;
}

.compact-meta {
  margin-top: 4px;
  font-size: 10px;
  color: #777;
  font-family: monospace;
}
</style>
