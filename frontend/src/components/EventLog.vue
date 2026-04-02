<template>
  <div class="event-log">
    <div class="header">
      <div class="header-left">
        <h3>{{ title }}</h3>
        <span class="count">{{ displayEvents.length }}</span>
      </div>
      <div class="header-actions">
        <button v-if="expandable" class="header-btn" type="button" @click="$emit('expand')">Expand</button>
        <button v-if="closable" class="header-btn" type="button" @click="$emit('close')">Close</button>
      </div>
    </div>
    <div class="events">
      <div
        v-for="(ev, i) in displayEvents"
        :key="eventKey(ev, i)"
        class="event"
        :class="eventClass(ev)"
      >
        <div class="event-top">
          <span class="time">{{ formatTime(ev.timestamp) }}</span>
          <span class="type" :class="badgeClass(eventView(ev).badgeTone)">{{ eventView(ev).badge }}</span>
          <span v-if="ev.display_agent || ev.agent_id" class="agent">{{ ev.display_agent || ev.agent_id }}</span>
        </div>
        <div class="title">{{ eventView(ev).title }}</div>
        <div v-if="eventView(ev).subtitle" class="detail">{{ eventView(ev).subtitle }}</div>
        <div v-if="eventView(ev).progress !== null" class="progress-shell">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${eventView(ev).progress}%` }"></div>
          </div>
          <span class="progress-label">{{ Math.max(0, Math.min(100, Number(eventView(ev).progress || 0))) }}%</span>
        </div>
        <div v-if="eventView(ev).lines.length" class="detail-list">
          <div v-for="(line, lineIndex) in eventView(ev).lines.slice(0, isExpanded(eventKey(ev, i)) ? eventView(ev).lines.length : 2)" :key="`${eventKey(ev, i)}-line-${lineIndex}`" class="detail-line">
            {{ line }}
          </div>
        </div>
        <button
          v-if="eventView(ev).expandable"
          class="event-expand"
          type="button"
          @click="toggleExpanded(eventKey(ev, i))"
        >
          {{ isExpanded(eventKey(ev, i)) ? 'Hide Details' : 'View Details' }}
        </button>
        <div v-if="isExpanded(eventKey(ev, i))" class="expanded">
          <div
            v-for="(section, sectionIndex) in eventView(ev).sections"
            :key="`${eventKey(ev, i)}-section-${sectionIndex}`"
            class="expanded-section"
          >
            <div class="expanded-label">{{ section.label }}</div>
            <div v-if="section.type === 'list'" class="expanded-list">
              <div v-for="(item, itemIndex) in section.items" :key="`${eventKey(ev, i)}-item-${itemIndex}`" class="expanded-item">
                {{ item }}
              </div>
            </div>
            <pre v-else-if="section.type === 'json'" class="expanded-pre json">{{ section.content }}</pre>
            <pre v-else-if="section.type === 'code'" class="expanded-pre code">{{ section.content }}</pre>
            <pre v-else class="expanded-pre">{{ section.content }}</pre>
          </div>
          <div v-if="ev.payload && Object.keys(ev.payload).length" class="expanded-section">
            <div class="expanded-label">Payload</div>
            <pre class="expanded-pre json">{{ prettyJson(ev.payload) }}</pre>
          </div>
          <div v-if="ev.refs && Object.keys(ev.refs).length" class="expanded-section">
            <div class="expanded-label">Refs</div>
            <pre class="expanded-pre json">{{ prettyJson(ev.refs) }}</pre>
          </div>
        </div>
      </div>
      <div v-if="!displayEvents.length" class="empty">No events yet.</div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, unref } from 'vue'
import { buildEventView } from '../lib/eventView.js'

const props = defineProps({
  events: { type: Array, default: () => [] },
  maxItems: { type: Number, default: 0 },
  title: { type: String, default: 'Live Events' },
  expandable: { type: Boolean, default: false },
  closable: { type: Boolean, default: false },
})

defineEmits(['expand', 'close'])

const expanded = reactive({})

const normalizedEvents = computed(() => {
  const source = unref(props.events)
  if (Array.isArray(source)) return source
  if (Array.isArray(source?.events)) return source.events
  if (Array.isArray(source?.value)) return source.value
  return []
})

const displayEvents = computed(() => {
  if (!props.maxItems || props.maxItems <= 0) {
    return normalizedEvents.value
  }
  return normalizedEvents.value.slice(0, props.maxItems)
})

function formatTime(ts) {
  return ts ? ts.slice(11, 19) : ''
}

function prettyJson(value) {
  return JSON.stringify(value || {}, null, 2)
}

function eventKey(event, index) {
  const refId = event?.refs?.artifact_id || event?.refs?.relation_id || ''
  const summary = String(event?.summary || '').slice(0, 24)
  return `${event.timestamp || 'event'}-${event.kind || 'kind'}-${event.agent_id || 'system'}-${refId}-${summary}-${index}`
}

function eventView(event) {
  return buildEventView(event)
}

function toggleExpanded(key) {
  expanded[key] = !expanded[key]
}

function isExpanded(key) {
  return Boolean(expanded[key])
}

function badgeClass(tone) {
  return `badge-${tone || 'default'}`
}

function eventClass(event) {
  return (event?.kind || 'event').replaceAll('_', '-')
}
</script>

<style scoped>
.event-log {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: #fff;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid #eee;
}
.header-left,
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
h3 {
  margin: 0;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #666;
}
.count {
  min-width: 24px;
  padding: 2px 6px;
  border: 1px solid #ddd;
  font-family: monospace;
  font-size: 10px;
  text-align: center;
}
.header-btn {
  padding: 4px 8px;
  border: 1px solid #111;
  background: #fff;
  font: inherit;
  font-size: 10px;
  text-transform: uppercase;
  cursor: pointer;
}
.header-btn:hover {
  background: #f5f5f5;
}
.events {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 12px 10px;
}
.event {
  padding: 8px 0;
  border-bottom: 1px solid #f3f3f3;
}
.event-top {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  line-height: 1.3;
}
.time {
  color: #999;
  font-family: monospace;
}
.type {
  color: #111;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  padding: 2px 6px;
  border: 1px solid #ddd;
  font-size: 9px;
  line-height: 1;
}
.type.badge-relation {
  border-color: #2f7d3b;
  color: #2f7d3b;
}
.type.badge-message {
  border-color: #2a6edb;
  color: #2a6edb;
}
.type.badge-experiment {
  border-color: #c76a16;
  color: #c76a16;
}
.type.badge-search {
  border-color: #1565c0;
  color: #1565c0;
}
.type.badge-error {
  border-color: #c62828;
  color: #c62828;
}
.title {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.35;
  color: #111;
  font-weight: 600;
}
.agent {
  margin-left: auto;
  color: #777;
  font-family: monospace;
  font-size: 9px;
}
.detail {
  margin-top: 3px;
  font-size: 11px;
  line-height: 1.35;
  color: #555;
}
.detail-list {
  margin-top: 5px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.detail-line {
  font-size: 10px;
  line-height: 1.35;
  color: #555;
}
.progress-shell {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
.progress-bar {
  flex: 1;
  height: 8px;
  border: 1px solid #ddd;
  background: #f5f5f5;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2a6edb, #2f7d3b);
}
.progress-label {
  font-size: 10px;
  color: #666;
  font-family: monospace;
}
.event-expand {
  margin-top: 8px;
  padding: 4px 8px;
  border: 1px solid #111;
  background: #fff;
  font: inherit;
  font-size: 10px;
  text-transform: uppercase;
  cursor: pointer;
}
.event-expand:hover {
  background: #f5f5f5;
}
.expanded {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.expanded-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.expanded-label {
  font-size: 10px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}
.expanded-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.expanded-item {
  font-size: 11px;
  line-height: 1.4;
  color: #444;
}
.expanded-pre {
  margin: 0;
  padding: 8px;
  border: 1px solid #eee;
  background: #fafafa;
  font-size: 10px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 220px;
  overflow: auto;
}
.expanded-pre.code {
  background: #f7f6f2;
}
.expanded-pre.json {
  background: #f8f9fb;
}
.event.finding-created,
.event.relation-created,
.event.reviewed-hypothesis {
  border-left: 3px solid #2e7d32;
  padding-left: 8px;
}
.event.search-completed,
.event.arxiv-search-completed,
.event.source-ingested,
.event.agent-thinking,
.event.downloading-source,
.event.download-source-progress,
.event.ingesting-source,
.event.ingested-search-source {
  border-left: 3px solid #1565c0;
  padding-left: 8px;
}
.event.experiment-started,
.event.experiment-queued,
.event.experiment-completed,
.event.experiment-failed {
  border-left: 3px solid #c76a16;
  padding-left: 8px;
}
.event.error {
  border-left: 3px solid #c62828;
  padding-left: 8px;
}
.empty {
  color: #999;
  font-size: 11px;
  font-style: italic;
  padding: 8px 0;
}
</style>
