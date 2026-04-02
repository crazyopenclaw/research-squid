<template>
  <div class="status-panel">
    <section class="section session-card">
      <h3>Session</h3>
      <div class="stat-row">
        <span class="label">Question</span>
        <span class="value question">{{ overview?.question || '--' }}</span>
      </div>
      <div class="stat-row">
        <span class="label">Status</span>
        <span class="value badge" :class="statusClass">{{ overview?.status || '--' }}</span>
      </div>
      <div v-if="overview?.research_plan?.director_summary" class="program-summary">
        {{ overview.research_plan.director_summary }}
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h4>Institute State</h4>
        <span class="pill">{{ percent(overview?.coverage?.ratio) }} covered</span>
      </div>
      <div class="stats-grid">
        <div class="mini-stat">
          <span>Subquestions</span>
          <strong>{{ overview?.coverage?.subquestions_covered || 0 }} / {{ overview?.coverage?.subquestions_total || 0 }}</strong>
        </div>
        <div class="mini-stat">
          <span>Pending work</span>
          <strong>{{ overview?.active_work?.count || 0 }}</strong>
        </div>
        <div class="mini-stat">
          <span>Open reviews</span>
          <strong>{{ overview?.contradictions_and_reviews?.count || 0 }}</strong>
        </div>
        <div class="mini-stat">
          <span>Hypotheses</span>
          <strong>{{ overview?.coverage?.hypotheses_count || 0 }}</strong>
        </div>
      </div>
    </section>

    <section v-if="overview?.research_plan" class="section">
      <h4>Research Plan</h4>
      <div v-if="overview.research_plan.subproblems?.length" class="list-block">
        <div class="block-label">Subproblems</div>
        <div class="card-list">
          <article
            v-for="subproblem in overview.research_plan.subproblems.slice(0, 8)"
            :key="subproblem.id"
            class="detail-card"
          >
            <div class="detail-top">
              <span class="tag">P{{ subproblem.priority }}</span>
              <span class="mono">{{ subproblem.id }}</span>
            </div>
            <div class="detail-title">{{ subproblem.question }}</div>
            <div v-if="subproblem.success_criteria" class="detail-copy">{{ subproblem.success_criteria }}</div>
            <div v-if="subproblem.assigned_agent" class="detail-meta">Agent: {{ subproblem.assigned_agent }}</div>
          </article>
        </div>
      </div>
      <div v-if="overview.research_plan.open_questions?.length" class="list-block">
        <div class="block-label">Open Questions</div>
        <ul class="bullet-list">
          <li v-for="question in overview.research_plan.open_questions.slice(0, 6)" :key="question">{{ question }}</li>
        </ul>
      </div>
      <div v-if="overview.research_plan.key_assumptions?.length" class="list-block">
        <div class="block-label">Key Assumptions</div>
        <ul class="bullet-list">
          <li v-for="assumption in overview.research_plan.key_assumptions.slice(0, 6)" :key="assumption">{{ assumption }}</li>
        </ul>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <h4>Active Work</h4>
        <span class="pill">{{ overview?.active_work?.count || 0 }}</span>
      </div>
      <div v-if="overview?.active_work?.items?.length" class="card-list compact-scroll">
        <article
          v-for="item in overview.active_work.items.slice(0, 10)"
          :key="item.id"
          class="detail-card"
        >
          <div class="detail-top">
            <span class="tag">{{ prettyType(item.kind) }}</span>
            <span class="status-tag" :class="item.status">{{ item.status }}</span>
          </div>
          <div class="detail-title">{{ item.title }}</div>
          <div v-if="item.summary" class="detail-copy">{{ item.summary }}</div>
          <div class="detail-meta">
            <span v-if="item.priority">Priority: {{ item.priority }}</span>
            <span v-if="item.assigned_agent"> | Agent: {{ item.assigned_agent }}</span>
          </div>
        </article>
      </div>
      <div v-else class="empty">No active work yet.</div>
    </section>

    <section class="section">
      <div class="section-head">
        <h4>Contradictions & Reviews</h4>
        <span class="pill">{{ overview?.contradictions_and_reviews?.count || 0 }}</span>
      </div>
      <div v-if="overview?.contradictions_and_reviews?.items?.length" class="card-list compact-scroll">
        <article
          v-for="item in overview.contradictions_and_reviews.items.slice(0, 8)"
          :key="item.id"
          class="detail-card"
        >
          <div class="detail-top">
            <span class="tag">review</span>
            <span class="status-tag">{{ item.status }}</span>
          </div>
          <div class="detail-title">{{ item.summary }}</div>
          <div class="detail-meta">{{ item.source_label }} | {{ item.target_label }}</div>
        </article>
      </div>
      <div v-else class="empty">No open contradictions yet.</div>
    </section>

    <section class="section">
      <div class="section-head">
        <h4>Shared Memory</h4>
        <span class="pill">{{ memoryResults.length }}</span>
      </div>
      <form class="memory-form" @submit.prevent="runMemorySearch">
        <input
          v-model="memoryQuery"
          type="text"
          placeholder="Search persisted chunks, notes, hypotheses, and results..."
        />
        <button type="submit" :disabled="memoryLoading || !memoryQuery.trim()">
          {{ memoryLoading ? 'Searching...' : 'Search' }}
        </button>
      </form>
      <div v-if="memoryError" class="memory-error">{{ memoryError }}</div>
      <div v-if="memoryResults.length" class="card-list compact-scroll">
        <article
          v-for="result in memoryResults"
          :key="result.id"
          class="detail-card memory-card"
        >
          <div class="detail-top">
            <span class="tag">{{ prettyType(result.kind) }}</span>
            <span class="mono">score {{ formatScore(result.score) }}</span>
          </div>
          <div class="detail-title">{{ result.title || result.canonical_id }}</div>
          <div v-if="result.source_url" class="detail-meta">{{ result.source_url }}</div>
          <div class="detail-copy">{{ truncate(result.text, 240) }}</div>
          <div class="detail-meta">
            <span v-if="result.agent_id">Agent: {{ result.agent_id }}</span>
          </div>
        </article>
      </div>
      <div v-else class="empty">
        Search the institute memory to inspect persisted evidence.
      </div>
    </section>

    <section class="section">
      <h4>Runtime Snapshot</h4>
      <div class="stats-grid">
        <div class="mini-stat">
          <span>Active agents</span>
          <strong>{{ overview?.agents?.active || 0 }} / {{ overview?.agents?.total || 0 }}</strong>
        </div>
        <div class="mini-stat">
          <span>Paused</span>
          <strong>{{ overview?.agents?.paused || 0 }}</strong>
        </div>
        <div class="mini-stat">
          <span>Contradictions</span>
          <strong>{{ overview?.contradiction_count || 0 }}</strong>
        </div>
        <div class="mini-stat">
          <span>Budget left</span>
          <strong>${{ Number(overview?.budget?.remaining || 0).toFixed(2) }}</strong>
        </div>
      </div>
      <div class="best-answer">
        <span class="confidence-badge" :class="confidenceClass">
          {{ overview?.best_answer?.label || '--' }}
        </span>
        <span v-if="overview?.best_answer?.claim" class="claim">{{ overview.best_answer.claim }}</span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { api } from '../api/index.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  overview: { type: Object, default: null },
})

const memoryQuery = ref('')
const memoryResults = ref([])
const memoryLoading = ref(false)
const memoryError = ref('')

const statusClass = computed(() => ({
  active: props.overview?.status === 'active',
  stopped: ['completed', 'failed', 'interrupted', 'cancelled'].includes(props.overview?.status),
  paused: props.overview?.status === 'paused',
}))

const confidenceClass = computed(() => {
  const c = props.overview?.best_answer?.confidence || 0
  if (c >= 0.85) return 'high'
  if (c >= 0.65) return 'moderate'
  if (c >= 0.45) return 'tentative'
  return 'weak'
})

async function runMemorySearch() {
  if (!props.sessionId || !memoryQuery.value.trim()) return
  memoryLoading.value = true
  memoryError.value = ''
  try {
    const result = await api.searchMemory(props.sessionId, memoryQuery.value.trim(), 8)
    memoryResults.value = result.results || []
  } catch (error) {
    memoryError.value = error.message
    memoryResults.value = []
  } finally {
    memoryLoading.value = false
  }
}

function percent(value) {
  const numeric = Number(value || 0)
  return `${(numeric * 100).toFixed(0)}%`
}

function prettyType(value) {
  return (value || 'item').replaceAll('_', ' ')
}

function formatScore(value) {
  return Number(value || 0).toFixed(2)
}

function truncate(value, length) {
  if (!value) return ''
  return value.length > length ? `${value.slice(0, length - 3)}...` : value
}
</script>

<style scoped>
.status-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.session-card {
  gap: 8px;
}
h3 {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}
h4 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #666;
  margin: 0;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}
.label {
  color: #666;
}
.value {
  font-weight: 500;
}
.question {
  max-width: 220px;
  text-align: right;
  line-height: 1.35;
}
.program-summary {
  font-size: 11px;
  color: #444;
  line-height: 1.45;
}
.badge {
  padding: 2px 8px;
  font-size: 10px;
  text-transform: uppercase;
}
.badge.active {
  background: #e8f5e9;
  color: #2e7d32;
}
.badge.stopped {
  background: #fce4ec;
  color: #c62828;
}
.badge.paused {
  background: #fff3e0;
  color: #e65100;
}
.pill,
.tag,
.status-tag,
.confidence-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 7px;
  border: 1px solid #ddd;
  font-size: 10px;
  text-transform: uppercase;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.mini-stat {
  border: 1px solid #eee;
  background: #fafafa;
  padding: 8px;
}
.mini-stat span {
  display: block;
  font-size: 10px;
  text-transform: uppercase;
  color: #666;
  margin-bottom: 4px;
}
.mini-stat strong {
  font-size: 12px;
}
.list-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.block-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #777;
}
.bullet-list {
  margin: 0;
  padding-left: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 11px;
  line-height: 1.4;
  color: #444;
}
.card-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.compact-scroll {
  max-height: 260px;
  overflow-y: auto;
  padding-right: 4px;
}
.detail-card {
  border: 1px solid #eee;
  background: #fafafa;
  padding: 10px;
}
.detail-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.detail-title {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
  color: #111;
}
.detail-copy {
  margin-top: 6px;
  font-size: 11px;
  line-height: 1.45;
  color: #444;
}
.detail-meta,
.mono {
  margin-top: 6px;
  font-size: 10px;
  color: #777;
  font-family: 'JetBrains Mono', monospace;
}
.status-tag.running,
.status-tag.open {
  color: #1565c0;
  border-color: #bbdefb;
}
.status-tag.pending {
  color: #6d4c41;
  border-color: #d7ccc8;
}
.status-tag.completed {
  color: #2e7d32;
  border-color: #c8e6c9;
}
.status-tag.failed,
.status-tag.blocked,
.status-tag.cancelled {
  color: #c62828;
  border-color: #ffcdd2;
}
.memory-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}
.memory-form input,
.memory-form button {
  font: inherit;
  font-size: 11px;
}
.memory-form input {
  min-width: 0;
  padding: 7px 8px;
  border: 1px solid #ccc;
}
.memory-form button {
  padding: 7px 10px;
  border: 1px solid #111;
  background: #fff;
  text-transform: uppercase;
  cursor: pointer;
}
.memory-form button:hover:not(:disabled) {
  background: #f5f5f5;
}
.memory-form button:disabled {
  opacity: 0.6;
  cursor: default;
}
.memory-card .detail-copy {
  white-space: pre-wrap;
}
.memory-error {
  color: #c62828;
  font-size: 11px;
}
.best-answer {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.confidence-badge.high {
  background: #e8f5e9;
  color: #2e7d32;
}
.confidence-badge.moderate {
  background: #e3f2fd;
  color: #1565c0;
}
.confidence-badge.tentative {
  background: #fff3e0;
  color: #e65100;
}
.confidence-badge.weak {
  background: #fce4ec;
  color: #c62828;
}
.claim {
  font-size: 11px;
  color: #555;
  line-height: 1.45;
}
.empty {
  color: #999;
  font-size: 11px;
  font-style: italic;
}
</style>
