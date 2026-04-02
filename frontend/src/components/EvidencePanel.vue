<template>
  <div class="evidence-panel">
    <div class="panel-header">
      <div class="header-info">
        <h3>Evidence</h3>
        <p class="subtitle">Findings extracted by research agents</p>
      </div>
      <div class="header-actions">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search findings..."
          class="search-input"
        />
        <select v-model="statusFilter" class="filter-select">
          <option value="">All statuses</option>
          <option value="confirmed">Confirmed</option>
          <option value="tentative">Tentative</option>
          <option value="refuted">Refuted</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <p>Loading findings...</p>
    </div>

    <div v-else-if="!filteredFindings.length" class="empty-state">
      <p>No findings yet. Findings will appear as agents make discoveries.</p>
    </div>

    <div v-else class="findings-table">
      <div class="table-header">
        <div class="col col-statement">Statement</div>
        <div class="col col-confidence">Confidence</div>
        <div class="col col-status">Status</div>
        <div class="col col-agent">Agent</div>
        <div class="col col-sources">Sources</div>
      </div>
      <div class="table-body">
        <article
          v-for="finding in filteredFindings"
          :key="finding.id"
          class="finding-row"
          :class="{ selected: selectedId === finding.id }"
          @click="selectFinding(finding)"
        >
          <div class="col col-statement">
            <div class="statement-text">{{ finding.text || finding.statement || 'Untitled' }}</div>
            <div class="statement-meta">{{ finding.id }}</div>
          </div>
          <div class="col col-confidence">
            <span class="confidence-badge" :class="confidenceClass(finding.confidence)">
              {{ percent(finding.confidence) }}
            </span>
          </div>
          <div class="col col-status">
            <span class="status-tag" :class="finding.status || 'tentative'">
              {{ finding.status || 'tentative' }}
            </span>
          </div>
          <div class="col col-agent">{{ finding.created_by || '--' }}</div>
          <div class="col col-sources">{{ finding.source_count || 0 }}</div>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  selectedId: { type: String, default: '' },
})

const emit = defineEmits(['select-finding'])

const findings = ref([])
const loading = ref(false)
const searchQuery = ref('')
const statusFilter = ref('')

const filteredFindings = computed(() => {
  let result = findings.value
  if (statusFilter.value) {
    result = result.filter((f) => (f.status || 'tentative') === statusFilter.value)
  }
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter((f) =>
      (f.text || f.statement || '').toLowerCase().includes(query)
    )
  }
  return result
})

async function loadFindings() {
  if (!props.sessionId) return
  loading.value = true
  try {
    const result = await api.getFindings(props.sessionId)
    findings.value = result.findings || result || []
  } catch (error) {
    findings.value = []
  } finally {
    loading.value = false
  }
}

function selectFinding(finding) {
  emit('select-finding', finding.id)
}

function percent(value) {
  const numeric = Number(value || 0)
  return `${(numeric * 100).toFixed(0)}%`
}

function confidenceClass(value) {
  const c = Number(value || 0)
  if (c >= 0.85) return 'high'
  if (c >= 0.65) return 'moderate'
  if (c >= 0.45) return 'tentative'
  return 'weak'
}

onMounted(() => {
  loadFindings()
})

watch(() => props.sessionId, () => {
  loadFindings()
})
</script>

<style scoped>
.evidence-panel {
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
  flex-wrap: wrap;
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

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.search-input {
  padding: 6px 10px;
  border: 1px solid #ccc;
  font-size: 11px;
  min-width: 180px;
}

.filter-select {
  padding: 6px 8px;
  border: 1px solid #ccc;
  font-size: 11px;
  background: #fff;
}

.loading-state,
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #666;
  font-size: 12px;
}

.findings-table {
  flex: 1;
  overflow: auto;
  min-height: 0;
}

.table-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 80px 90px 120px 70px;
  gap: 8px;
  padding: 8px 16px;
  background: #fafafa;
  border-bottom: 1px solid #eee;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #666;
  position: sticky;
  top: 0;
}

.table-body {
  display: flex;
  flex-direction: column;
}

.finding-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 80px 90px 120px 70px;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.1s;
}

.finding-row:hover {
  background: #fafafa;
}

.finding-row.selected {
  background: #f0f7ff;
}

.col {
  display: flex;
  align-items: center;
  min-width: 0;
}

.col-statement {
  flex-direction: column;
  align-items: flex-start;
}

.statement-text {
  font-size: 12px;
  font-weight: 500;
  line-height: 1.35;
  color: #111;
}

.statement-meta {
  font-size: 10px;
  color: #777;
  font-family: monospace;
  margin-top: 2px;
}

.confidence-badge {
  padding: 2px 6px;
  border: 1px solid currentColor;
  font-size: 10px;
  font-family: monospace;
}

.confidence-badge.high {
  color: #2e7d32;
  background: #e8f5e9;
}

.confidence-badge.moderate {
  color: #1565c0;
  background: #e3f2fd;
}

.confidence-badge.tentative {
  color: #e65100;
  background: #fff3e0;
}

.confidence-badge.weak {
  color: #c62828;
  background: #fce4ec;
}

.status-tag {
  padding: 2px 6px;
  border: 1px solid currentColor;
  font-size: 9px;
  text-transform: uppercase;
}

.status-tag.confirmed {
  color: #2e7d32;
}

.status-tag.tentative {
  color: #666;
}

.status-tag.refuted {
  color: #c62828;
}

.col-agent,
.col-sources {
  font-size: 11px;
  color: #555;
}
</style>
