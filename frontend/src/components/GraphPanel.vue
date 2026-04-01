<template>
  <div class="graph-panel" ref="containerRef">
    <div class="graph-header">
      <h3>Knowledge DAG</h3>
      <div class="graph-controls">
        <button @click="refresh" :disabled="loading">
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
        <button @click="fitView">Fit</button>
        <div class="legend">
          <span class="legend-item finding">Finding</span>
          <span class="legend-item experiment">Experiment</span>
          <span class="legend-item cluster">Cluster</span>
        </div>
      </div>
    </div>
    <div class="graph-stats">
      <span>{{ nodeCount }} nodes</span>
      <span>{{ edgeCount }} edges</span>
      <span v-if="selectedNode">Selected: {{ selectedNode.label }}</span>
    </div>
    <div ref="graphRef" class="graph-canvas"></div>

    <!-- Selected Node Detail -->
    <div v-if="selectedNode" class="node-detail">
      <div class="detail-header">
        <span class="detail-type" :class="selectedNode.type">{{ selectedNode.type }}</span>
        <span class="detail-id">{{ selectedNode.id }}</span>
        <button class="close-btn" @click="selectedNode = null">×</button>
      </div>
      <div class="detail-body">
        <div v-if="selectedNode.type === 'Finding'" class="finding-detail">
          <div class="claim">{{ selectedNode.props.claim }}</div>
          <div class="meta">
            <span class="conf-badge" :class="confClass(selectedNode.props.confidence)">
              {{ (selectedNode.props.confidence * 100).toFixed(0) }}%
            </span>
            <span class="evidence">{{ selectedNode.props.evidence_type }}</span>
            <span class="tier">Tier {{ selectedNode.props.min_source_tier }}</span>
            <span v-if="selectedNode.props.has_numerical_verification" class="verified">✓ verified</span>
          </div>
          <div class="rationale">{{ selectedNode.props.confidence_rationale }}</div>
          <div class="sources" v-if="selectedNode.props.source_urls?.length">
            <div v-for="url in selectedNode.props.source_urls.slice(0, 3)" :key="url" class="source-url">
              {{ url }}
            </div>
          </div>
          <div class="agent-info">
            Agent: {{ selectedNode.props.agent_id }} | Cycle: {{ selectedNode.props.cycle_posted }}
          </div>
        </div>
        <div v-else-if="selectedNode.type === 'Experiment'" class="experiment-detail">
          <div class="goal">{{ selectedNode.props.goal }}</div>
          <div class="meta">
            <span class="status-badge" :class="selectedNode.props.status">
              {{ selectedNode.props.status }}
            </span>
            <span>{{ selectedNode.props.backend_type }}</span>
          </div>
        </div>
        <div v-else class="generic-detail">
          <pre>{{ JSON.stringify(selectedNode.props, null, 2) }}</pre>
        </div>
      </div>
      <div class="detail-edges" v-if="connectedEdges.length">
        <h5>Connections</h5>
        <div v-for="edge in connectedEdges" :key="edge.id" class="edge-item">
          <span class="edge-type" :class="edge.type.toLowerCase()">{{ edge.type }}</span>
          <span class="edge-dir">{{ edge.direction }}</span>
          <span class="edge-other">{{ edge.otherId }}</span>
          <span v-if="edge.counter_claim" class="counter-claim">
            Counter: {{ edge.counter_claim }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { Network } from 'vis-network'
import { api } from '../api/index.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  autoRefresh: { type: Boolean, default: true },
  refreshInterval: { type: Number, default: 10000 },
})

const containerRef = ref(null)
const graphRef = ref(null)
const loading = ref(false)
const nodeCount = ref(0)
const edgeCount = ref(0)
const selectedNode = ref(null)
const connectedEdges = ref([])
const dagData = ref({ nodes: [], edges: [] })

let network = null
let refreshTimer = null

// Node colors by type
const NODE_COLORS = {
  Finding: { background: '#e8f5e9', border: '#2e7d32', highlight: { background: '#c8e6c9', border: '#1b5e20' } },
  Experiment: { background: '#e3f2fd', border: '#1565c0', highlight: { background: '#bbdefb', border: '#0d47a1' } },
  ExperimentRun: { background: '#fff3e0', border: '#e65100', highlight: { background: '#ffe0b2', border: '#bf360c' } },
  Cluster: { background: '#fce4ec', border: '#c62828', highlight: { background: '#f8bbd0', border: '#b71c1c' } },
  Agent: { background: '#f3e5f5', border: '#7b1fa2', highlight: { background: '#e1bee7', border: '#4a148c' } },
}

// Edge colors by type
const EDGE_COLORS = {
  SUPPORTS: '#2e7d32',
  CONTRADICTS: '#c62828',
  EXTENDS: '#1565c0',
  REFUTES: '#e65100',
  SYNTHESIZES: '#7b1fa2',
  PRODUCED_BY: '#ff8f00',
  TESTED: '#00838f',
}

function initNetwork() {
  if (!graphRef.value) return

  const options = {
    nodes: {
      shape: 'box',
      font: { size: 11, face: 'JetBrains Mono, monospace' },
      borderWidth: 2,
      margin: { top: 8, bottom: 8, left: 12, right: 12 },
      widthConstraint: { maximum: 200 },
    },
    edges: {
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
      font: { size: 9, color: '#666', strokeWidth: 2, strokeColor: '#fff' },
      smooth: { type: 'cubicBezier', roundness: 0.3 },
      width: 2,
    },
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -50,
        centralGravity: 0.01,
        springLength: 150,
        springConstant: 0.02,
      },
      stabilization: { iterations: 100 },
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      selectConnectedEdges: true,
    },
  }

  network = new Network(graphRef.value, { nodes: [], edges: [] }, options)

  network.on('selectNode', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      const node = dagData.value.nodes.find(n => n.id === nodeId)
      if (node) {
        selectedNode.value = node
        connectedEdges.value = getConnectedEdges(nodeId)
      }
    }
  })

  network.on('deselectNode', () => {
    // Keep selectedNode for detail panel — user closes manually
  })
}

async function refresh() {
  loading.value = true
  try {
    const data = await api.getDag(props.sessionId)
    dagData.value = data
    updateGraph(data)
  } catch (e) {
    console.error('Failed to load DAG:', e)
  } finally {
    loading.value = false
  }
}

function updateGraph(data) {
  if (!network) return

  const visNodes = (data.nodes || []).map(n => {
    const type = n.labels?.[0] || 'Unknown'
    const props = n.props || n.properties || {}
    const colors = NODE_COLORS[type] || { background: '#f5f5f5', border: '#999' }

    let label = type
    if (type === 'Finding') {
      const claim = props.claim || ''
      label = claim.length > 40 ? claim.slice(0, 40) + '...' : claim
    } else if (type === 'Experiment') {
      label = props.goal?.slice(0, 40) || props.backend_type || type
    } else if (type === 'ExperimentRun') {
      label = `Run: ${props.status || '?'}`
    } else if (type === 'Cluster') {
      label = props.central_claim?.slice(0, 40) || type
    }

    return {
      id: props.id || Math.random().toString(),
      label,
      color: colors,
      title: `${type}: ${props.claim || props.goal || props.id || ''}`,
      font: { color: '#111' },
      // Store original data for detail panel
      _type: type,
      _props: props,
    }
  })

  const visEdges = (data.edges || []).map((e, i) => {
    const type = e.type || 'RELATED'
    const color = EDGE_COLORS[type] || '#999'
    const props = e.props || e.properties || {}

    return {
      id: `edge_${i}`,
      from: e.src || e.source,
      to: e.tgt || e.target,
      label: type,
      color: { color, highlight: color },
      dashes: type === 'CONTRADICTS' ? [5, 5] : false,
      _type: type,
      _props: props,
    }
  })

  network.setData({ nodes: visNodes, edges: visEdges })
  nodeCount.value = visNodes.length
  edgeCount.value = visEdges.length

  // Store for detail panel lookups
  dagData.value.nodes = visNodes.map(n => ({
    id: n.id,
    label: n.label,
    type: n._type,
    props: n._props,
  }))
  dagData.value.edges = visEdges.map(e => ({
    id: e.id,
    from: e.from,
    to: e.to,
    type: e._type,
    props: e._props,
  }))
}

function getConnectedEdges(nodeId) {
  return (dagData.value.edges || [])
    .filter(e => e.from === nodeId || e.to === nodeId)
    .map(e => ({
      id: e.id,
      type: e.type,
      direction: e.from === nodeId ? '→ outgoing' : '← incoming',
      otherId: e.from === nodeId ? e.to : e.from,
      counter_claim: e.props?.counter_claim,
    }))
}

function fitView() {
  if (network) network.fit({ animation: true })
}

function confClass(c) {
  if (!c) return 'weak'
  if (c >= 0.85) return 'high'
  if (c >= 0.65) return 'moderate'
  if (c >= 0.45) return 'tentative'
  return 'weak'
}

onMounted(async () => {
  await nextTick()
  initNetwork()
  await refresh()
  if (props.autoRefresh) {
    refreshTimer = setInterval(refresh, props.refreshInterval)
  }
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (network) network.destroy()
})

watch(() => props.sessionId, () => refresh())
</script>

<style scoped>
.graph-panel { position: relative; height: 100%; display: flex; flex-direction: column; }
.graph-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid #eee; }
.graph-header h3 { font-size: 13px; text-transform: uppercase; letter-spacing: 1px; margin: 0; }
.graph-controls { display: flex; gap: 8px; align-items: center; }
.graph-controls button { padding: 4px 10px; border: 1px solid #111; background: #fff; font-family: inherit; font-size: 10px; cursor: pointer; text-transform: uppercase; }
.graph-controls button:hover { background: #f5f5f5; }
.legend { display: flex; gap: 8px; margin-left: 12px; }
.legend-item { font-size: 9px; text-transform: uppercase; padding: 2px 6px; }
.legend-item.finding { background: #e8f5e9; color: #2e7d32; }
.legend-item.experiment { background: #e3f2fd; color: #1565c0; }
.legend-item.cluster { background: #fce4ec; color: #c62828; }
.graph-stats { padding: 4px 12px; font-size: 10px; color: #666; border-bottom: 1px solid #f0f0f0; display: flex; gap: 12px; }
.graph-canvas { flex: 1; min-height: 400px; }

/* Node detail panel */
.node-detail { position: absolute; top: 80px; right: 12px; width: 320px; max-height: calc(100% - 100px); background: #fff; border: 1px solid #ddd; overflow-y: auto; z-index: 10; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.detail-header { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-bottom: 1px solid #eee; }
.detail-type { font-size: 10px; text-transform: uppercase; padding: 2px 6px; font-weight: 600; }
.detail-type.Finding { background: #e8f5e9; color: #2e7d32; }
.detail-type.Experiment { background: #e3f2fd; color: #1565c0; }
.detail-type.ExperimentRun { background: #fff3e0; color: #e65100; }
.detail-type.Cluster { background: #fce4ec; color: #c62828; }
.detail-id { font-family: monospace; font-size: 10px; color: #999; flex: 1; }
.close-btn { border: none; background: none; font-size: 16px; cursor: pointer; color: #999; }
.close-btn:hover { color: #111; }
.detail-body { padding: 12px; }
.claim { font-size: 12px; margin-bottom: 8px; line-height: 1.4; }
.meta { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.conf-badge { font-family: monospace; font-size: 10px; padding: 1px 6px; font-weight: 600; }
.conf-badge.high { background: #e8f5e9; color: #2e7d32; }
.conf-badge.moderate { background: #e3f2fd; color: #1565c0; }
.conf-badge.tentative { background: #fff3e0; color: #e65100; }
.conf-badge.weak { background: #fce4ec; color: #c62828; }
.evidence, .tier, .verified { font-size: 10px; color: #666; }
.verified { color: #2e7d32; font-weight: 600; }
.rationale { font-size: 11px; color: #555; font-style: italic; margin-bottom: 8px; }
.sources { margin-bottom: 8px; }
.source-url { font-size: 9px; color: #1565c0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agent-info { font-size: 10px; color: #999; }
.goal { font-size: 12px; margin-bottom: 8px; }
.status-badge { font-size: 10px; padding: 1px 6px; text-transform: uppercase; }
.status-badge.pending { background: #fff3e0; color: #e65100; }
.status-badge.running { background: #e3f2fd; color: #1565c0; }
.status-badge.completed { background: #e8f5e9; color: #2e7d32; }
.status-badge.failed { background: #fce4ec; color: #c62828; }
.generic-detail pre { font-size: 10px; background: #fafafa; padding: 8px; overflow-x: auto; }
.detail-edges { border-top: 1px solid #eee; padding: 8px 12px; }
.detail-edges h5 { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: #666; margin-bottom: 6px; }
.edge-item { display: flex; gap: 6px; align-items: center; font-size: 10px; padding: 2px 0; }
.edge-type { padding: 1px 4px; font-weight: 600; font-size: 9px; text-transform: uppercase; }
.edge-type.supports { background: #e8f5e9; color: #2e7d32; }
.edge-type.contradicts { background: #fce4ec; color: #c62828; }
.edge-type.extends { background: #e3f2fd; color: #1565c0; }
.edge-type.refutes { background: #fff3e0; color: #e65100; }
.edge-type.produced_by { background: #fff8e1; color: #ff8f00; }
.edge-type.tested { background: #e0f7fa; color: #00838f; }
.edge-dir { color: #999; }
.edge-other { font-family: monospace; color: #555; }
.counter-claim { font-size: 9px; color: #c62828; font-style: italic; }
</style>
