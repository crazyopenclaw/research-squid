<template>
  <div class="finding-tab">
    <div class="panel-header">
      <h3>Finding Inspector</h3>
      <p class="intro">Select a finding in the graph or evidence table to view details.</p>
    </div>

    <div v-if="!findingId" class="empty-state">
      <p>Click a finding node in the graph or select a row in Evidence mode.</p>
    </div>

    <div v-else-if="loading" class="loading-state">
      <p>Loading finding...</p>
    </div>

    <div v-else-if="finding" class="finding-content">
      <section class="section hero">
        <div class="hero-top">
          <div>
            <div class="finding-title">{{ finding.text || finding.statement || 'Untitled Finding' }}</div>
            <div class="finding-meta">{{ finding.id }}</div>
          </div>
          <span class="status-badge" :class="finding.status || 'tentative'">
            {{ finding.status || 'tentative' }}
          </span>
        </div>
      </section>

      <section v-if="finding.statement" class="section">
        <h4>Statement</h4>
        <div class="statement">{{ finding.statement }}</div>
      </section>

      <section v-if="finding.evidence?.length" class="section">
        <h4>Supporting Evidence</h4>
        <div class="evidence-list">
          <article
            v-for="item in finding.evidence"
            :key="item.id"
            class="evidence-card"
          >
            <div class="evidence-source">{{ item.source_type || 'Source' }}</div>
            <div class="evidence-text">{{ truncate(item.text || item.summary, 180) }}</div>
            <div v-if="item.confidence" class="evidence-meta">Confidence: {{ percent(item.confidence) }}</div>
          </article>
        </div>
      </section>

      <section class="section">
        <h4>Metadata</h4>
        <div class="meta-grid">
          <div v-if="finding.confidence"><span>Confidence</span>{{ percent(finding.confidence) }}</div>
          <div v-if="finding.created_by"><span>Agent</span>{{ finding.created_by }}</div>
          <div v-if="finding.created_at"><span>Created</span>{{ formatTime(finding.created_at) }}</div>
          <div v-if="finding.source_count"><span>Sources</span>{{ finding.source_count }}</div>
        </div>
      </section>

      <section v-if="finding.tags?.length" class="section">
        <h4>Tags</h4>
        <div class="tag-list">
          <span v-for="tag in finding.tags" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </section>

      <section v-if="finding.related_hypotheses?.length" class="section">
        <h4>Related Hypotheses</h4>
        <div class="compact-list">
          <div v-for="hyp in finding.related_hypotheses" :key="hyp.id" class="compact-card">
            <div class="compact-title">{{ truncate(hyp.statement || hyp.text, 80) }}</div>
            <div class="compact-meta">{{ hyp.id }} | {{ percent(hyp.confidence) }}</div>
          </div>
        </div>
      </section>
    </div>

    <div v-else class="empty-state">
      <p>Finding not found or not yet available.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api } from '../../api/index.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  findingId: { type: String, default: '' },
})

const finding = ref(null)
const loading = ref(false)

watch(
  () => props.findingId,
  async (value) => {
    if (!value) {
      finding.value = null
      return
    }
    loading.value = true
    try {
      const result = await api.getFinding(props.sessionId, value)
      finding.value = result.finding || result
    } catch (error) {
      finding.value = null
    } finally {
      loading.value = false
    }
  },
  { immediate: true }
)

function percent(value) {
  const numeric = Number(value || 0)
  return `${(numeric * 100).toFixed(0)}%`
}

function formatTime(timestamp) {
  if (!timestamp) return '--'
  return new Date(timestamp).toLocaleString()
}

function truncate(value, length) {
  const text = String(value || '')
  return text.length > length ? `${text.slice(0, length - 3)}...` : text
}
</script>

<style scoped>
.finding-tab {
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

.finding-content {
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

.finding-title {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
}

.finding-meta {
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

.status-badge.confirmed {
  color: #2f7d3b;
}

.status-badge.tentative {
  color: #666;
}

.status-badge.refuted {
  color: #bf3a3a;
}

h4 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #666;
  margin: 0 0 8px;
}

.statement {
  font-size: 12px;
  line-height: 1.5;
  color: #333;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-card {
  border: 1px solid #eee;
  background: #fafafa;
  padding: 10px;
}

.evidence-source {
  font-size: 10px;
  text-transform: uppercase;
  color: #777;
  margin-bottom: 4px;
}

.evidence-text {
  font-size: 11px;
  line-height: 1.45;
  color: #333;
}

.evidence-meta {
  margin-top: 6px;
  font-size: 10px;
  color: #777;
  font-family: monospace;
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
