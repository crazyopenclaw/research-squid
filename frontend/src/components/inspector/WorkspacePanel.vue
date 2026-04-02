<template>
  <div class="workspace-panel">
    <div class="panel-header">
      <div>
        <h3>Workspace Inspector</h3>
        <p class="intro">Browse agent files, memory, and OpenCode sessions.</p>
      </div>
    </div>

    <div v-if="!agentId" class="empty-state">
      Select an agent icon in the graph to inspect its workspace.
    </div>

    <div v-else class="inspector-content">
      <!-- File Browser -->
      <section class="section">
        <div class="section-head">
          <h4>Files</h4>
          <span v-if="files.length" class="pill">{{ files.length }}</span>
        </div>
        <div v-if="filesLoading" class="empty">Loading files...</div>
        <div v-else-if="files.length" class="file-list">
          <div
            v-for="file in files.slice(0, fileLimit)"
            :key="file.path"
            class="file-item"
            :class="{ active: selectedFile?.path === file.path }"
            @click="selectFile(file)"
          >
            <span class="file-name">{{ file.path }}</span>
            <span class="file-size">{{ formatSize(file.size_kb) }}</span>
          </div>
          <button
            v-if="files.length > fileLimit"
            class="show-more"
            @click="fileLimit += 20"
          >
            Show {{ files.length - fileLimit }} more...
          </button>
        </div>
        <div v-else class="empty">No files found.</div>
      </section>

      <!-- File Content Preview -->
      <section v-if="selectedFile" class="section">
        <div class="section-head">
          <h4>{{ selectedFile.path }}</h4>
          <button class="close-btn" @click="selectedFile = null">×</button>
        </div>
        <div v-if="fileContentLoading" class="empty">Loading...</div>
        <pre v-else class="file-content">{{ fileContent }}</pre>
      </section>

      <!-- Quick Links to Key Files -->
      <section class="section">
        <div class="section-head">
          <h4>Key Files</h4>
        </div>
        <div class="key-files">
          <button
            v-for="keyFile in keyFiles"
            :key="keyFile.path"
            class="key-file-btn"
            :class="{ active: selectedFile?.path === keyFile.path }"
            @click="loadKeyFile(keyFile.path)"
          >
            {{ keyFile.label }}
          </button>
        </div>
      </section>

      <!-- OpenCode Sessions -->
      <section class="section">
        <div class="section-head">
          <h4>OpenCode Sessions</h4>
          <span v-if="opencodeSessions.length" class="pill">{{ opencodeSessions.length }}</span>
        </div>
        <div v-if="opencodeLoading" class="empty">Loading sessions...</div>
        <div v-else-if="opencodeSessions.length" class="session-list">
          <div
            v-for="session in opencodeSessions"
            :key="session.opencode_session_id"
            class="session-item"
          >
            <div class="session-top">
              <span class="session-topic">{{ session.topic }}</span>
              <span class="session-status" :class="session.status">
                {{ session.status }}
              </span>
            </div>
            <div class="session-meta">
              <span>{{ session.turn_count }} turns</span>
              <span>${{ session.total_cost_usd?.toFixed(4) || '0.0000' }}</span>
              <span v-if="session.files_produced?.length">
                {{ session.files_produced.length }} files
              </span>
            </div>
          </div>
        </div>
        <div v-else class="empty">No OpenCode sessions found.</div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { api } from '../../api/index.js'

const props = defineProps({
  sessionId: { type: String, required: true },
  agentId: { type: String, default: '' },
})

const files = ref([])
const filesLoading = ref(false)
const selectedFile = ref(null)
const fileContent = ref('')
const fileContentLoading = ref(false)
const fileLimit = ref(20)

const opencodeSessions = ref([])
const opencodeLoading = ref(false)

const keyFiles = computed(() => [
  { path: 'memory.md', label: '🧠 memory.md' },
  { path: 'goals.md', label: '🎯 goals.md' },
  { path: 'hypotheses.md', label: '💡 hypotheses.md' },
  { path: 'beliefs.json', label: '📊 beliefs.json' },
  { path: 'notes.md', label: '📝 notes.md' },
])

async function loadFiles() {
  if (!props.agentId) return
  filesLoading.value = true
  try {
    const result = await api.listWorkspaceFiles(props.sessionId, props.agentId)
    files.value = result.files || []
  } catch (error) {
    console.error('Failed to load workspace files:', error)
    files.value = []
  } finally {
    filesLoading.value = false
  }
}

async function loadOpenCodeSessions() {
  if (!props.agentId) return
  opencodeLoading.value = true
  try {
    const result = await api.getOpenCodeSessions(props.sessionId, props.agentId)
    opencodeSessions.value = result.sessions || []
  } catch (error) {
    console.error('Failed to load OpenCode sessions:', error)
    opencodeSessions.value = []
  } finally {
    opencodeLoading.value = false
  }
}

async function selectFile(file) {
  selectedFile.value = file
  fileContentLoading.value = true
  fileContent.value = ''
  try {
    const result = await api.getWorkspaceFile(props.sessionId, props.agentId, file.path)
    fileContent.value = result.content || '(empty file)'
  } catch (error) {
    fileContent.value = `Error loading file: ${error.message}`
  } finally {
    fileContentLoading.value = false
  }
}

async function loadKeyFile(path) {
  const file = files.value.find(f => f.path === path) || { path, size_kb: 0 }
  await selectFile(file)
}

function formatSize(kb) {
  if (!kb) return ''
  if (kb < 1) return '< 1 KB'
  if (kb < 1024) return `${Math.round(kb)} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

watch(() => props.agentId, async (newId) => {
  if (!newId) {
    files.value = []
    opencodeSessions.value = []
    selectedFile.value = null
    fileContent.value = ''
    return
  }
  await Promise.all([loadFiles(), loadOpenCodeSessions()])
}, { immediate: true })
</script>

<style scoped>
.workspace-panel {
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

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

h4 {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #666;
  margin: 0;
}

.pill {
  min-width: 24px;
  padding: 2px 6px;
  border: 1px solid #ddd;
  font-family: monospace;
  font-size: 10px;
  text-align: center;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
}

.file-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid #eee;
  cursor: pointer;
  font-size: 11px;
}

.file-item:hover {
  background: #f5f5f5;
}

.file-item.active {
  border-color: #2a6edb;
  background: #e8f0fe;
}

.file-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
}

.file-size {
  color: #777;
  font-size: 10px;
}

.show-more {
  padding: 6px;
  border: 1px dashed #ccc;
  background: #fafafa;
  font-size: 10px;
  cursor: pointer;
  text-align: center;
}

.show-more:hover {
  background: #f0f0f0;
}

.file-content {
  margin: 0;
  padding: 10px;
  border: 1px solid #eee;
  background: #fafafa;
  font-size: 10px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}

.close-btn {
  padding: 0 4px;
  border: none;
  background: none;
  font-size: 16px;
  cursor: pointer;
  color: #666;
}

.close-btn:hover {
  color: #111;
}

.key-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.key-file-btn {
  padding: 4px 8px;
  border: 1px solid #ddd;
  background: #fff;
  font-size: 10px;
  cursor: pointer;
}

.key-file-btn:hover {
  background: #f5f5f5;
}

.key-file-btn.active {
  border-color: #2a6edb;
  background: #e8f0fe;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.session-item {
  border: 1px solid #eee;
  padding: 8px;
}

.session-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.session-topic {
  font-size: 11px;
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-status {
  font-size: 9px;
  text-transform: uppercase;
  padding: 1px 4px;
  border: 1px solid currentColor;
}

.session-status.completed {
  color: #2f7d3b;
}

.session-status.failed {
  color: #bf3a3a;
}

.session-status.abandoned {
  color: #c76a16;
}

.session-status.output_limit_reached {
  color: #9c27b0;
}

.session-meta {
  display: flex;
  gap: 12px;
  font-size: 10px;
  color: #777;
}

.empty {
  margin-top: 8px;
  font-size: 11px;
  color: #999;
  font-style: italic;
}
</style>
