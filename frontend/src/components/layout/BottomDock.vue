<template>
  <div class="bottom-dock" :class="{ expanded: expanded }">
    <div class="dock-header" @click="toggleExpand">
      <div class="header-left">
        <span class="toggle-icon">{{ expanded ? '▼' : '▲' }}</span>
        <span class="title">Events</span>
        <span class="count">{{ events.length }}</span>
      </div>
      <div v-if="!expanded" class="header-preview">
        <span v-if="latestEvent" class="preview-text">
          {{ latestEvent.display_agent || 'System' }}: {{ latestEvent.title }}
        </span>
      </div>
    </div>
    <div v-if="expanded" class="dock-body">
      <EventLog
        :events="events"
        :maxItems="50"
        :expandable="false"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EventLog from '../EventLog.vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
  expanded: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle'])

const latestEvent = computed(() => props.events[0] || null)

function toggleExpand() {
  emit('toggle', !props.expanded)
}
</script>

<style scoped>
.bottom-dock {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-top: 1px solid #e0e0e0;
  flex: 0 0 auto;
  min-height: 32px;
  max-height: 32px;
  transition: max-height 0.2s ease-out;
}
.bottom-dock.expanded {
  max-height: 240px;
}
.dock-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  cursor: pointer;
  user-select: none;
  background: #f8f8f8;
  border-bottom: 1px solid transparent;
}
.bottom-dock.expanded .dock-header {
  border-bottom-color: #e0e0e0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toggle-icon {
  font-size: 10px;
  color: #666;
}
.title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #333;
}
.count {
  font-size: 10px;
  font-family: monospace;
  color: #999;
  background: #eee;
  padding: 1px 5px;
}
.header-preview {
  flex: 1;
  margin-left: 16px;
  overflow: hidden;
}
.preview-text {
  font-size: 11px;
  color: #666;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}
.dock-body {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}
</style>
