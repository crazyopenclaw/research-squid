<template>
  <div class="cluster-tab">
    <div class="panel-header">
      <h3>Cluster Inspector</h3>
      <p class="intro">Select a cluster in the graph to view its members and summary.</p>
    </div>

    <div v-if="!clusterId" class="empty-state">
      <p>Click a cluster hull or group label in the graph to inspect.</p>
    </div>

    <div v-else-if="loading" class="loading-state">
      <p>Loading cluster...</p>
    </div>

    <div v-else-if="cluster" class="cluster-content">
      <section class="section hero">
        <div class="hero-top">
          <div>
            <div class="cluster-title">{{ cluster.name || cluster.label || 'Cluster' }}</div>
            <div class="cluster-meta">{{ cluster.id }}</div>
          </div>
          <span class="member-count">{{ cluster.members?.length || 0 }} members</span>
        </div>
      </section>

      <section v-if="cluster.summary" class="section">
        <h4>Summary</h4>
        <div class="summary">{{ cluster.summary }}</div>
      </section>

      <section class="section">
        <h4>Members</h4>
        <div class="member-list">
          <article
            v-for="member in cluster.members"
            :key="member.id"
            class="member-card"
            :class="member.type"
          >
            <div class="member-top">
              <span class="member-type">{{ member.type }}</span>
              <span class="member-id">{{ member.id }}</span>
            </div>
            <div class="member-label">{{ member.label || member.name || member.statement || 'Unnamed' }}</div>
          </article>
        </div>
      </section>

      <section v-if="cluster.common_tags?.length" class="section">
        <h4>Common Tags</h4>
        <div class="tag-list">
          <span v-for="tag in cluster.common_tags" :key="tag" class="tag">{{ tag }}</span>
        </div>
      </section>

      <section v-if="cluster.statistics" class="section">
        <h4>Statistics</h4>
        <div class="stats-grid">
          <div v-if="cluster.statistics.avg_confidence !== undefined">
            <span>Avg Confidence</span>{{ percent(cluster.statistics.avg_confidence) }}
          </div>
          <div v-if="cluster.statistics.findings_count !== undefined">
            <span>Findings</span>{{ cluster.statistics.findings_count }}
          </div>
          <div v-if="cluster.statistics.experiments_count !== undefined">
            <span>Experiments</span>{{ cluster.statistics.experiments_count }}
          </div>
          <div v-if="cluster.statistics.agents_count !== undefined">
            <span>Agents</span>{{ cluster.statistics.agents_count }}
          </div>
        </div>
      </section>

      <section v-if="cluster.key_insight" class="section">
        <h4>Key Insight</h4>
        <div class="insight">{{ cluster.key_insight }}</div>
      </section>
    </div>

    <div v-else class="empty-state">
      <p>Cluster not found or not yet available.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api } from '../../api/index.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  clusterId: { type: String, default: '' },
})

const cluster = ref(null)
const loading = ref(false)

watch(
  () => props.clusterId,
  async (value) => {
    if (!value) {
      cluster.value = null
      return
    }
    loading.value = true
    try {
      cluster.value = await api.getCluster(props.sessionId, value)
    } catch (error) {
      cluster.value = null
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
</script>

<style scoped>
.cluster-tab {
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

.cluster-content {
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

.cluster-title {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
}

.cluster-meta {
  font-family: monospace;
  font-size: 10px;
  color: #777;
  margin-top: 4px;
}

.member-count {
  font-size: 10px;
  padding: 2px 6px;
  border: 1px solid #ddd;
  background: #fafafa;
}

h4 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #666;
  margin: 0 0 8px;
}

.summary,
.insight {
  font-size: 12px;
  line-height: 1.5;
  color: #333;
}

.member-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
}

.member-card {
  border: 1px solid #eee;
  background: #fafafa;
  padding: 8px;
}

.member-card.agent {
  border-left: 3px solid #1565c0;
}

.member-card.finding {
  border-left: 3px solid #2e7d32;
}

.member-card.experiment {
  border-left: 3px solid #c76a16;
}

.member-card.hypothesis {
  border-left: 3px solid #7b1fa2;
}

.member-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.member-type {
  font-size: 9px;
  text-transform: uppercase;
  color: #777;
}

.member-id {
  font-size: 9px;
  font-family: monospace;
  color: #999;
}

.member-label {
  font-size: 11px;
  font-weight: 500;
  color: #333;
  line-height: 1.35;
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  font-size: 11px;
}

.stats-grid span {
  display: block;
  font-size: 10px;
  text-transform: uppercase;
  color: #777;
  margin-bottom: 3px;
}
</style>
