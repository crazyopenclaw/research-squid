<template>
  <div class="agent-tab">
    <div class="panel-header">
      <div>
        <h3>Agent Inspector</h3>
        <p class="intro">Graph selection drives this panel. The activity feed is the runtime source of truth.</p>
      </div>
      <button v-if="agentId" @click="inspectById(agentId)" :disabled="loading" class="refresh-btn">
        {{ loading ? 'Loading...' : 'Refresh' }}
      </button>
    </div>

    <div v-if="!agentId" class="empty-state">
      Select an agent icon in the graph to inspect its current work.
    </div>

    <div v-else-if="data" class="inspector-content">
      <section class="section hero">
        <div class="hero-top">
          <div>
            <div class="agent-name">{{ data.agent_data?.display_name || data.agent_id }}</div>
            <div class="agent-meta">{{ data.agent_id }}</div>
            <div v-if="data.current_status_text" class="agent-stage">{{ data.current_status_text }}</div>
          </div>
          <span class="status-badge" :class="data.agent_data?.status || 'sleeping'">
            {{ data.agent_data?.status || 'unknown' }}
          </span>
        </div>
        <div class="hero-grid">
          <div><span>Archetype</span>{{ data.agent_data?.archetype_name || 'Unassigned' }}</div>
          <div><span>Specialty</span>{{ data.persona?.specialty || 'general' }}</div>
          <div><span>Findings</span>{{ data.findings_count || 0 }}</div>
          <div><span>Experiments</span>{{ data.experiments_count || 0 }}</div>
          <div><span>Focus</span>{{ data.current_focus || data.agent_data?.line_of_inquiry || '--' }}</div>
          <div><span>Model tier</span>{{ data.persona?.model_tier || '--' }}</div>
        </div>
      </section>

      <section v-if="data.current_hypothesis" class="section">
        <h4>Current Hypothesis</h4>
        <div class="hypothesis">
          <span class="claim">{{ data.current_hypothesis.text }}</span>
          <span class="conf">{{ percent(data.current_hypothesis.confidence) }}</span>
        </div>
      </section>

      <section class="section activity-section">
        <div class="section-head">
          <h4>Activity Feed</h4>
          <span class="count">{{ data.activity_feed?.length || 0 }}</span>
        </div>
        <div v-if="data.activity_feed?.length" class="activity-feed">
          <article
            v-for="(item, index) in data.activity_feed"
            :key="`${item.timestamp}-${item.kind}-${index}`"
            class="activity-item"
            :class="activityClass(item.kind)"
          >
            <div class="activity-top">
              <span class="activity-time">{{ formatTime(item.timestamp) }}</span>
              <span class="activity-type">{{ prettyType(item.kind) }}</span>
            </div>
            <div class="activity-title">{{ item.title }}</div>
            <div v-if="item.summary" class="activity-detail">{{ item.summary }}</div>
            <div v-if="hasRefs(item)" class="activity-meta">
              <span v-for="meta in refChips(item.refs)" :key="meta" class="meta-chip">{{ meta }}</span>
            </div>
            <button
              v-if="item.expandable"
              class="expand-btn"
              type="button"
              @click="toggleExpanded(index)"
            >
              {{ isExpanded(index) ? 'Hide Step' : 'View Step' }}
            </button>
            <div v-if="isExpanded(index)" class="activity-expanded">
              <div v-if="item.payload && Object.keys(item.payload).length" class="expanded-block">
                <div class="expanded-label">Payload</div>
                <pre>{{ prettyJson(item.payload) }}</pre>
              </div>
              <div v-if="item.refs && Object.keys(item.refs).length" class="expanded-block">
                <div class="expanded-label">Refs</div>
                <pre>{{ prettyJson(item.refs) }}</pre>
              </div>
            </div>
          </article>
        </div>
        <div v-else class="empty">No agent activity recorded yet.</div>
      </section>

      <section v-if="artifactSections.length" class="section">
        <h4>Recent Public Artifacts</h4>
        <div class="artifact-groups">
          <div v-for="section in artifactSections" :key="section.label" class="artifact-group">
            <div class="artifact-head">
              <span>{{ section.label }}</span>
              <span>{{ section.items.length }}</span>
            </div>
            <div class="compact-list">
              <div
                v-for="item in section.items"
                :key="item.id"
                class="compact-card"
              >
                <div class="compact-title">{{ artifactTitle(item) }}</div>
                <div class="compact-meta">{{ item.id }}</div>
                <div v-if="artifactSummary(item)" class="compact-summary">{{ artifactSummary(item) }}</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-if="data.experiments?.length" class="section">
        <h4>Experiments</h4>
        <div class="compact-list">
          <div v-for="experiment in data.experiments" :key="experiment.id" class="compact-card">
            <div class="compact-top">
              <span>{{ experiment.status || 'pending' }}</span>
              <span>{{ experiment.id }}</span>
            </div>
            <div class="compact-title">{{ experiment.spec_expected_outcome || experiment.id }}</div>
            <div v-if="experiment.spec_code" class="compact-summary">{{ truncate(experiment.spec_code, 220) }}</div>
          </div>
        </div>
      </section>

      <section class="section">
        <h4>Persona Snapshot</h4>
        <div v-if="data.persona" class="persona-grid">
          <div><span>Skepticism</span>{{ percent(data.persona.skepticism_level) }}</div>
          <div><span>Source strictness</span>{{ percent(data.persona.source_strictness) }}</div>
          <div><span>Experiment appetite</span>{{ percent(data.persona.experiment_appetite) }}</div>
          <div><span>Model tier</span>{{ data.persona.model_tier || 'inherited' }}</div>
          <div><span>Motivation</span>{{ data.persona.motivation || 'truth_seeking' }}</div>
          <div><span>Style</span>{{ data.persona.collaboration_style || 'collaborative' }}</div>
        </div>
        <div v-else class="empty">No persona set.</div>
      </section>

      <section class="section">
        <h4>Agent Relations</h4>
        <div v-if="data.relation_summary?.length" class="relations">
          <div
            v-for="relation in data.relation_summary.slice(0, 8)"
            :key="`${relation.direction}-${relation.type}-${relation.other_agent_id}`"
            class="relation-card"
          >
            <div class="relation-top">
              <span class="relation-type" :class="String(relation.type || '').toLowerCase()">{{ relation.type }}</span>
              <span class="relation-direction">{{ relation.direction }}</span>
            </div>
            <div class="relation-other">{{ relation.other_label }}</div>
            <div class="relation-meta">{{ relation.other_archetype }} | {{ relation.count }} links</div>
            <div v-if="relation.sample_claims?.length" class="relation-claim">{{ relation.sample_claims[0] }}</div>
          </div>
        </div>
        <div v-else class="empty">No agent-to-agent relations yet.</div>
      </section>

      <section class="section">
        <h4>Interview Agent</h4>
        <textarea v-model="interviewPrompt" rows="2" placeholder="Ask this agent a question..."></textarea>
        <button @click="interview" :disabled="!props.agentId || !interviewPrompt || interviewing" class="interview-btn">
          {{ interviewing ? 'Interviewing...' : 'Ask' }}
        </button>
        <div v-if="interviewResponse" class="interview-response">
          <pre>{{ interviewResponse }}</pre>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '../../api/index.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  agentId: { type: String, default: '' },
  refreshKey: { type: Number, default: 0 },
})

const data = ref(null)
const loading = ref(false)
const interviewPrompt = ref('')
const interviewResponse = ref('')
const interviewing = ref(false)
const expandedItems = ref({})

const artifactSections = computed(() => {
  const artifacts = data.value?.recent_artifacts || {}
  const sections = []
  if (artifacts.notes?.length) sections.push({ label: 'Notes', items: artifacts.notes.slice(0, 6) })
  if (artifacts.assumptions?.length) sections.push({ label: 'Assumptions', items: artifacts.assumptions.slice(0, 6) })
  if (artifacts.hypotheses?.length) sections.push({ label: 'Hypotheses', items: artifacts.hypotheses.slice(0, 6) })
  if (artifacts.findings?.length) sections.push({ label: 'Findings', items: artifacts.findings.slice(0, 6) })
  return sections
})

watch(
  () => props.agentId,
  async (value) => {
    if (!value) {
      data.value = null
      interviewResponse.value = ''
      expandedItems.value = {}
      return
    }
    await inspectById(value)
  },
  { immediate: true }
)

watch(() => props.refreshKey, async () => {
  if (props.agentId) {
    await inspectById(props.agentId)
  }
})

async function inspectById(target) {
  if (!target) return
  loading.value = true
  try {
    data.value = await api.getAgentDetail(props.sessionId, target)
    expandedItems.value = {}
  } catch (error) {
    alert(error.message)
  } finally {
    loading.value = false
  }
}

async function interview() {
  interviewing.value = true
  interviewResponse.value = ''
  try {
    const result = await api.interviewAgent(props.sessionId, {
      agent_id: props.agentId,
      prompt: interviewPrompt.value,
    })
    interviewResponse.value = result.grounded_response || 'No response.'
  } catch (error) {
    interviewResponse.value = `Error: ${error.message}`
  } finally {
    interviewing.value = false
  }
}

function percent(value) {
  const numeric = Number(value || 0)
  return `${(numeric * 100).toFixed(0)}%`
}

function formatTime(timestamp) {
  return timestamp ? timestamp.slice(11, 19) : ''
}

function prettyType(value) {
  return (value || 'event').replaceAll('_', ' ')
}

function activityClass(type) {
  return (type || 'event').replaceAll('_', '-')
}

function toggleExpanded(index) {
  expandedItems.value = {
    ...expandedItems.value,
    [index]: !expandedItems.value[index],
  }
}

function isExpanded(index) {
  return Boolean(expandedItems.value[index])
}

function prettyJson(value) {
  return JSON.stringify(value || {}, null, 2)
}

function hasRefs(item) {
  return Boolean(item?.refs && Object.keys(item.refs).length)
}

function refChips(refs) {
  const chips = []
  for (const [key, value] of Object.entries(refs || {})) {
    if (Array.isArray(value)) {
      if (value.length) chips.push(`${key}: ${value.length}`)
      continue
    }
    if (value) chips.push(`${key}: ${String(value)}`)
  }
  return chips
}

function artifactTitle(item) {
  return item?.title || item?.statement || item?.content || item?.text || item?.id
}

function artifactSummary(item) {
  return item?.content || item?.rationale || item?.summary || item?.text || ''
}

function truncate(value, length) {
  const text = String(value || '')
  return text.length > length ? `${text.slice(0, length - 3)}...` : text
}
</script>

<style scoped>
.agent-tab {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}
.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
h3 {
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 0 0 6px;
}
.intro {
  margin: 0;
  font-size: 11px;
  color: #666;
  line-height: 1.4;
}
.refresh-btn,
button {
  padding: 6px 12px;
  border: 1px solid #111;
  background: #fff;
  font-family: inherit;
  font-size: 11px;
  cursor: pointer;
  text-transform: uppercase;
}
button:hover {
  background: #f5f5f5;
}
.empty-state {
  border: 1px dashed #ddd;
  padding: 14px;
  font-size: 11px;
  color: #666;
}
.inspector-content {
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
.agent-name {
  font-size: 13px;
  font-weight: 700;
}
.agent-meta {
  font-family: monospace;
  font-size: 10px;
  color: #777;
  margin-top: 2px;
}
.agent-stage {
  margin-top: 6px;
  font-size: 11px;
  color: #2a6edb;
}
.status-badge {
  font-size: 10px;
  padding: 2px 6px;
  text-transform: uppercase;
  border: 1px solid currentColor;
}
.status-badge.active,
.status-badge.researching {
  color: #2f7d3b;
}
.status-badge.paused,
.status-badge.sleeping {
  color: #666;
}
.status-badge.failed,
.status-badge.interrupted {
  color: #bf3a3a;
}
.hero-grid,
.persona-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin-top: 10px;
  font-size: 11px;
}
.hero-grid span,
.persona-grid span {
  display: block;
  font-size: 10px;
  text-transform: uppercase;
  color: #777;
  margin-bottom: 3px;
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
  margin-bottom: 8px;
}
.count {
  min-width: 24px;
  padding: 2px 6px;
  border: 1px solid #ddd;
  font-family: monospace;
  font-size: 10px;
  text-align: center;
}
.hypothesis {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
  margin-top: 8px;
}
.claim {
  flex: 1;
  font-size: 12px;
  line-height: 1.45;
}
.conf {
  font-family: monospace;
  font-size: 13px;
  font-weight: 700;
}
.compact-card {
  border: 1px solid #eee;
  background: #fafafa;
  padding: 10px;
}
.compact-top,
.artifact-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 10px;
  color: #666;
  text-transform: uppercase;
}
.compact-title {
  font-size: 12px;
  font-weight: 600;
  color: #111;
  line-height: 1.35;
}
.compact-summary {
  margin-top: 6px;
  font-size: 11px;
  line-height: 1.45;
  color: #444;
}
.compact-meta {
  margin-top: 6px;
  font-size: 10px;
  color: #777;
  font-family: monospace;
}
.compact-list,
.artifact-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.artifact-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.activity-feed {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 360px;
  overflow-y: auto;
  padding-right: 4px;
}
.activity-item {
  border: 1px solid #eee;
  padding: 8px;
}
.activity-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.activity-time {
  font-family: monospace;
  font-size: 10px;
  color: #888;
}
.activity-type {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: #444;
}
.activity-title {
  font-size: 11px;
  font-weight: 600;
  color: #111;
}
.activity-detail {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.45;
  color: #555;
}
.activity-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.expand-btn {
  width: 100%;
  margin-top: 8px;
}
.activity-expanded {
  margin-top: 8px;
  border-top: 1px solid #f0f0f0;
  padding-top: 8px;
}
.expanded-block + .expanded-block {
  margin-top: 8px;
}
.expanded-label {
  font-size: 10px;
  text-transform: uppercase;
  color: #777;
  margin-bottom: 4px;
}
.activity-expanded pre {
  margin: 0;
  padding: 8px;
  border: 1px solid #eee;
  background: #fafafa;
  font-size: 10px;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 220px;
  overflow: auto;
}
.meta-chip {
  padding: 2px 6px;
  border: 1px solid #ddd;
  font-size: 10px;
  line-height: 1;
}
.activity-item.agent-thinking,
.activity-item.search-completed,
.activity-item.source-ingested,
.activity-item.note-created,
.activity-item.assumption-created,
.activity-item.hypothesis-created {
  border-left: 3px solid #1565c0;
  padding-left: 8px;
}
.activity-item.finding-created,
.activity-item.relation-created,
.activity-item.reviewed-hypothesis {
  border-left: 3px solid #2e7d32;
  padding-left: 8px;
}
.activity-item.experiment-started,
.activity-item.experiment-queued,
.activity-item.experiment-completed,
.activity-item.experiment-failed {
  border-left: 3px solid #c76a16;
  padding-left: 8px;
}
.activity-item.error,
.activity-item.artifact-refuted {
  border-left: 3px solid #c62828;
  padding-left: 8px;
}
.relations {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.relation-card {
  border: 1px solid #eee;
  padding: 8px;
}
.relation-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}
.relation-type {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 5px;
  text-transform: uppercase;
}
.relation-type.supports {
  background: #eaf8ef;
  color: #2f7d3b;
}
.relation-type.contradicts {
  background: #fff0f0;
  color: #bf3a3a;
}
.relation-type.extends {
  background: #eaf3ff;
  color: #2a6edb;
}
.relation-type.refutes {
  background: #fff3e8;
  color: #c76a16;
}
.relation-direction {
  font-size: 10px;
  color: #777;
  text-transform: uppercase;
}
.relation-other {
  font-size: 12px;
  font-weight: 600;
}
.relation-meta {
  font-size: 10px;
  color: #777;
  margin-top: 2px;
}
.relation-claim {
  font-size: 11px;
  color: #444;
  margin-top: 6px;
  line-height: 1.4;
}
textarea {
  width: 100%;
  min-width: 0;
  padding: 6px;
  border: 1px solid #ccc;
  font-family: inherit;
  font-size: 11px;
}
.interview-btn {
  width: 100%;
  margin-top: 8px;
}
.interview-response {
  margin-top: 8px;
}
.interview-response pre {
  background: #fafafa;
  border: 1px solid #eee;
  padding: 8px;
  font-size: 11px;
  white-space: pre-wrap;
  max-height: 220px;
  overflow-y: auto;
}
.empty {
  margin-top: 8px;
  font-size: 11px;
  color: #999;
  font-style: italic;
}
</style>
