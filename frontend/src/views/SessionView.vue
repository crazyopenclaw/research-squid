<template>
  <div class="session-view">
    <TopBar
      :question="store.graphView.value?.question || store.session.value?.question"
      :experiments="store.overview.value?.experiments || {}"
      :budget="store.budget.value"
      :status="store.overview.value?.status || store.session.value?.status"
      :createdAt="store.session.value?.created_at"
      @pause="handlePause"
      @resume="handleResume"
      @stop="handleStop"
    />

    <div class="main-content">
      <LeftSidebar
        :currentMode="store.centerMode.value"
        @change-mode="handleModeChange"
      />

      <div class="center-pane">
        <GraphPanel
          v-if="store.centerMode.value === 'graph'"
          :sessionId="sessionId"
          :graph="store.graphView.value"
          :selectedAgentId="selectedAgentId"
          :events="liveEvents"
          :loading="store.loading.value"
          @select-agent="handleSelectAgent"
          @select-station="handleSelectStation"
          @select-edge="handleSelectEdge"
          @refresh="store.refreshSessionState()"
        />
        <div v-if="liveEventsOpen" class="graph-live-overlay">
          <EventLog
            :events="liveEvents"
            title="Live Event Console"
            :closable="true"
            @close="liveEventsOpen = false"
          />
        </div>
        <EvidencePanel
          v-else-if="store.centerMode.value === 'evidence'"
          :sessionId="sessionId"
          :selectedId="selectedFindingId"
          @select-finding="handleSelectFinding"
        />
        <ExperimentsPanel
          v-else-if="store.centerMode.value === 'experiments'"
          :sessionId="sessionId"
          :selectedId="selectedExperimentId"
          @select-experiment="handleSelectExperiment"
        />
        <ReportPanel
          v-else-if="store.centerMode.value === 'report'"
          :sessionId="sessionId"
        />
      </div>

      <aside class="inspector-panel">
        <div class="inspector-tabs">
          <button
            v-for="tab in inspectorTabs"
            :key="tab.id"
            class="tab-btn"
            :class="{ active: store.inspectorTab.value === tab.id }"
            @click="store.inspectorTab.value = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>
        <div class="inspector-body">
          <OverviewTab
            v-if="store.inspectorTab.value === 'overview'"
            :sessionId="sessionId"
            :overview="store.overview.value"
          />
          <AgentTab
            v-else-if="store.inspectorTab.value === 'agent'"
            :sessionId="sessionId"
            :refreshKey="store.syncVersion.value"
            :agentId="selectedAgentId"
          />
          <WorkspacePanel
            v-else-if="store.inspectorTab.value === 'workspace'"
            :sessionId="sessionId"
            :agentId="selectedAgentId"
          />
          <FindingTab
            v-else-if="store.inspectorTab.value === 'finding'"
            :sessionId="sessionId"
            :findingId="selectedFindingId"
          />
          <ExperimentTab
            v-else-if="store.inspectorTab.value === 'experiment'"
            :sessionId="sessionId"
            :experimentId="selectedExperimentId"
          />
          <ClusterTab
            v-else-if="store.inspectorTab.value === 'cluster'"
            :sessionId="sessionId"
            :clusterId="selectedClusterId"
          />
        </div>

        <section class="sidebar-events">
          <EventLog
            :events="liveEvents"
            :maxItems="6"
            :expandable="true"
            @expand="liveEventsOpen = true"
          />
        </section>
      </aside>
    </div>

    <BottomDock
      :events="liveEvents"
      :expanded="store.bottomDockExpanded.value"
      @toggle="store.bottomDockExpanded.value = $event"
    />

    <BudgetWarningModal
      :show="showBudgetWarning"
      :budget="store.budget.value"
      :session-id="sessionId"
      @continue="handleContinueBudget"
      @stop="handleStop"
      @close="showBudgetWarning = false"
    />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useSessionStore } from '../store/session.js'
import TopBar from '../components/layout/TopBar.vue'
import LeftSidebar from '../components/layout/LeftSidebar.vue'
import BottomDock from '../components/layout/BottomDock.vue'
import GraphPanel from '../components/GraphPanel.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import ExperimentsPanel from '../components/ExperimentsPanel.vue'
import ReportPanel from '../components/ReportPanel.vue'
import OverviewTab from '../components/inspector/OverviewTab.vue'
import AgentTab from '../components/inspector/AgentTab.vue'
import FindingTab from '../components/inspector/FindingTab.vue'
import ExperimentTab from '../components/inspector/ExperimentTab.vue'
import ClusterTab from '../components/inspector/ClusterTab.vue'
import BudgetWarningModal from '../components/BudgetWarningModal.vue'
import WorkspacePanel from '../components/inspector/WorkspacePanel.vue'
import { api } from '../api/index.js'

const route = useRoute()
const store = useSessionStore()
const sessionId = computed(() => route.params.id)
const liveEvents = computed(() => (Array.isArray(store.events.value) ? store.events.value : []))
const selectedAgentId = ref('')
const selectedFindingId = ref('')
const selectedExperimentId = ref('')
const selectedClusterId = ref('')
const showBudgetWarning = ref(false)

const inspectorTabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'agent', label: 'Agent' },
  { id: 'workspace', label: 'Workspace' },
  { id: 'finding', label: 'Finding' },
  { id: 'experiment', label: 'Experiment' },
  { id: 'cluster', label: 'Cluster' },
]

function handleModeChange(mode) {
  store.centerMode.value = mode
}

function handleSelectAgent(agentId) {
  selectedAgentId.value = agentId
  store.inspectorTab.value = 'agent'
}

function handleSelectFinding(findingId) {
  selectedFindingId.value = findingId
  store.inspectorTab.value = 'finding'
}

function handleSelectExperiment(experimentId) {
  selectedExperimentId.value = experimentId
  store.inspectorTab.value = 'experiment'
}

function handleSelectStation(stationType) {
  if (stationType === 'archive') {
    store.centerMode.value = 'evidence'
  } else if (stationType === 'lab' || stationType === 'experiment') {
    store.centerMode.value = 'experiments'
  }
}

function handleSelectEdge(edgeData) {
  selectedAgentId.value = edgeData.agentId
  store.inspectorTab.value = 'agent'
}

function handlePause() {
  console.log('Pause session')
}

function handleResume() {
  console.log('Resume session')
}

function handleStop() {
  console.log('Stop session')
}

function toggleViewportLock(enabled) {
  document.documentElement.classList.toggle('session-route', enabled)
  document.body.classList.toggle('session-route', enabled)
}

onMounted(() => {
  toggleViewportLock(true)
  store.load(sessionId.value)
})

onUnmounted(() => {
  store.disconnect()
  toggleViewportLock(false)
})

watch(
  sessionId,
  async (nextId, prevId) => {
    if (!nextId || nextId === prevId) return
    selectedAgentId.value = ''
    await store.load(nextId)
  }
)

watch(
  () => store.agents.value,
  (agents) => {
    if (!agents.length) {
      selectedAgentId.value = ''
      return
    }
    if (!agents.some((agent) => agent.id === selectedAgentId.value)) {
      selectedAgentId.value = agents[0].id
    }
  },
  { immediate: true }
)

watch(
  () => store.budget.value?.is_warning,
  (isWarning) => {
    if (isWarning) {
      showBudgetWarning.value = true
    }
  }
)

async function handleContinueBudget(payload) {
  await api.continueSession(sessionId.value, payload)
  showBudgetWarning.value = false
}
</script>

<style scoped>
:global(html.session-route),
:global(body.session-route) {
  height: 100%;
  overflow: hidden;
}

.session-view {
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}

.main-content {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.center-pane {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  border-right: 1px solid #e0e0e0;
}

.mode-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
}

.mode-placeholder h3 {
  font-size: 16px;
  margin-bottom: 8px;
  color: #333;
}

.mode-placeholder p {
  font-size: 13px;
}

.inspector-panel {
  width: 360px;
  flex: 0 0 360px;
  display: flex;
  flex-direction: column;
  background: #fafafa;
  overflow: hidden;
}

.inspector-tabs {
  display: flex;
  border-bottom: 1px solid #e0e0e0;
  background: #fff;
  flex: 0 0 auto;
}

.tab-btn {
  flex: 1;
  padding: 8px 4px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #666;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}

.tab-btn:hover {
  color: #333;
}

.tab-btn.active {
  color: #111;
  border-bottom-color: #111;
}

.inspector-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.tab-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 24px;
  text-align: center;
  color: #999;
  font-size: 12px;
}
</style>
