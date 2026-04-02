<template>
  <div class="experiments-panel">
    <div class="panel-header">
      <div class="header-info">
        <h3>Experiments</h3>
        <p class="subtitle">Sandbox experiments testing hypotheses</p>
      </div>
      <div class="header-actions">
        <select v-model="statusFilter" class="filter-select">
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <p>Loading experiments...</p>
    </div>

    <div v-else-if="!columns.pending.length && !columns.active.length && !columns.completed.length" class="empty-state">
      <p>No experiments yet. Agents will queue experiments to test hypotheses.</p>
    </div>

    <div v-else class="kanban-board">
      <div class="kanban-column">
        <div class="column-header">
          <span class="column-title">Pending</span>
          <span class="column-count">{{ columns.pending.length }}</span>
        </div>
        <div class="column-body">
          <article
            v-for="experiment in columns.pending"
            :key="experiment.id"
            class="experiment-card"
            :class="{ selected: selectedId === experiment.id }"
            @click="selectExperiment(experiment)"
          >
            <div class="card-header">
              <span class="exp-id">{{ experiment.id }}</span>
            </div>
            <div class="card-title">{{ experiment.spec_expected_outcome || 'Experiment' }}</div>
            <div class="card-meta">{{ experiment.created_by || 'Unassigned' }}</div>
          </article>
        </div>
      </div>

      <div class="kanban-column">
        <div class="column-header running">
          <span class="column-title">Running</span>
          <span class="column-count">{{ columns.active.length }}</span>
        </div>
        <div class="column-body">
          <article
            v-for="experiment in columns.active"
            :key="experiment.id"
            class="experiment-card running"
            :class="{ selected: selectedId === experiment.id }"
            @click="selectExperiment(experiment)"
          >
            <div class="card-header">
              <span class="exp-id">{{ experiment.id }}</span>
              <span class="running-indicator">Running</span>
            </div>
            <div class="card-title">{{ experiment.spec_expected_outcome || 'Experiment' }}</div>
            <div class="card-meta">{{ experiment.created_by || 'Unassigned' }}</div>
          </article>
        </div>
      </div>

      <div class="kanban-column">
        <div class="column-header completed">
          <span class="column-title">Completed</span>
          <span class="column-count">{{ columns.completed.length }}</span>
        </div>
        <div class="column-body">
          <article
            v-for="experiment in columns.completed"
            :key="experiment.id"
            class="experiment-card"
            :class="[experiment.status, { selected: selectedId === experiment.id }]"
            @click="selectExperiment(experiment)"
          >
            <div class="card-header">
              <span class="exp-id">{{ experiment.id }}</span>
              <span class="status-indicator" :class="experiment.status">{{ experiment.status }}</span>
            </div>
            <div class="card-title">{{ experiment.spec_expected_outcome || 'Experiment' }}</div>
            <div v-if="experiment.actual_outcome" class="card-outcome">{{ truncate(experiment.actual_outcome, 60) }}</div>
            <div class="card-meta">{{ experiment.created_by || 'Unassigned' }}</div>
          </article>
        </div>
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

const emit = defineEmits(['select-experiment'])

const experiments = ref([])
const loading = ref(false)
const statusFilter = ref('')

const columns = computed(() => {
  const pending = experiments.value.filter((e) => ['pending', 'queued'].includes(e.status))
  const active = experiments.value.filter((e) => e.status === 'running')
  const completed = experiments.value.filter((e) => ['completed', 'failed'].includes(e.status))

  if (statusFilter.value === 'pending') return { pending, active: [], completed: [] }
  if (statusFilter.value === 'running') return { pending: [], active, completed: [] }
  if (statusFilter.value === 'completed' || statusFilter.value === 'failed') return { pending: [], active: [], completed }
  if (statusFilter.value === 'queued') return { pending: pending.filter((e) => e.status === 'queued'), active: [], completed: [] }

  return { pending, active, completed }
})

async function loadExperiments() {
  if (!props.sessionId) return
  loading.value = true
  try {
    const result = await api.getExperiments(props.sessionId)
    experiments.value = result.experiments || result || []
  } catch (error) {
    experiments.value = []
  } finally {
    loading.value = false
  }
}

function selectExperiment(experiment) {
  emit('select-experiment', experiment.id)
}

function truncate(value, length) {
  const text = String(value || '')
  return text.length > length ? `${text.slice(0, length - 3)}...` : text
}

onMounted(() => {
  loadExperiments()
})

watch(() => props.sessionId, () => {
  loadExperiments()
})
</script>

<style scoped>
.experiments-panel {
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

.kanban-board {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 12px;
  min-height: 0;
  overflow: auto;
}

.kanban-column {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid #eee;
  background: #fafafa;
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
  background: #fff;
}

.column-header.running {
  background: #e3f2fd;
}

.column-header.completed {
  background: #f5f5f5;
}

.column-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
}

.column-count {
  padding: 2px 6px;
  border: 1px solid #ddd;
  font-size: 10px;
  font-family: monospace;
}

.column-body {
  flex: 1;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  min-height: 0;
}

.experiment-card {
  border: 1px solid #ddd;
  background: #fff;
  padding: 10px;
  cursor: pointer;
  transition: border-color 0.1s, box-shadow 0.1s;
}

.experiment-card:hover {
  border-color: #999;
}

.experiment-card.selected {
  border-color: #1565c0;
  box-shadow: 0 0 0 2px rgba(21, 101, 192, 0.2);
}

.experiment-card.running {
  border-left: 3px solid #1565c0;
}

.experiment-card.completed {
  border-left: 3px solid #2e7d32;
}

.experiment-card.failed {
  border-left: 3px solid #c62828;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.exp-id {
  font-size: 10px;
  font-family: monospace;
  color: #777;
}

.running-indicator {
  font-size: 9px;
  padding: 2px 5px;
  background: #e3f2fd;
  color: #1565c0;
  text-transform: uppercase;
}

.status-indicator {
  font-size: 9px;
  padding: 2px 5px;
  text-transform: uppercase;
}

.status-indicator.completed {
  background: #e8f5e9;
  color: #2e7d32;
}

.status-indicator.failed {
  background: #fce4ec;
  color: #c62828;
}

.card-title {
  font-size: 11px;
  font-weight: 600;
  line-height: 1.35;
  color: #111;
}

.card-outcome {
  margin-top: 4px;
  font-size: 10px;
  color: #555;
  line-height: 1.4;
}

.card-meta {
  margin-top: 6px;
  font-size: 10px;
  color: #777;
}
</style>
