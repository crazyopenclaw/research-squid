<template>
  <nav class="left-sidebar">
    <button
      v-for="mode in modes"
      :key="mode.id"
      class="nav-item"
      :class="{ active: currentMode === mode.id }"
      @click="$emit('change-mode', mode.id)"
      :title="mode.label"
    >
      <span class="icon">{{ mode.icon }}</span>
      <span class="label">{{ mode.label }}</span>
    </button>
  </nav>
</template>

<script setup>
defineProps({
  currentMode: { type: String, default: 'graph' },
})

defineEmits(['change-mode'])

const modes = [
  { id: 'graph', label: 'Graph', icon: '◉' },
  { id: 'evidence', label: 'Evidence', icon: '◈' },
  { id: 'experiments', label: 'Experiments', icon: '◇' },
  { id: 'report', label: 'Report', icon: '¶' },
]
</script>

<style scoped>
.left-sidebar {
  display: flex;
  flex-direction: column;
  width: 64px;
  background: #f5f5f5;
  border-right: 1px solid #e0e0e0;
  flex: 0 0 auto;
}
.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 12px 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #666;
  font: inherit;
  transition: background 0.15s, color 0.15s;
}
.nav-item:hover {
  background: #eee;
  color: #333;
}
.nav-item.active {
  background: #fff;
  color: #111;
  border-left: 3px solid #111;
  margin-left: -1px;
}
.icon {
  font-size: 18px;
  line-height: 1;
}
.label {
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}
</style>
