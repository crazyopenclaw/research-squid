const DEFAULT_AGENT_LABELS = {
  system: 'System',
  director: 'Director',
  controller: 'Controller',
  'debate-system': 'Debate System',
  adjudicator: 'Adjudicator',
}

const KIND_BADGES = {
  relation_created: 'relation',
  message_sent: 'message',
  experiment_started: 'experiment',
  experiment_completed: 'experiment',
  experiment_failed: 'experiment',
  note_created: 'artifact',
  assumption_created: 'artifact',
  hypothesis_created: 'artifact',
  finding_created: 'artifact',
  arxiv_search_completed: 'search',
  search_completed: 'search',
  source_ingested: 'search',
  error: 'error',
}

export function createDefaultAgentLabels() {
  return { ...DEFAULT_AGENT_LABELS }
}

export function rememberAgentLabel(labels, agentId, label) {
  if (!labels || !agentId || !label) return
  labels[agentId] = label
}

export function lookupAgentLabel(labels, agentId) {
  if (!agentId) return ''
  return labels?.[agentId] || agentId
}

function shortText(value, limit = 160) {
  const text = String(value || '').trim().replaceAll('\n', ' ')
  if (!text) return ''
  return text.length > limit ? `${text.slice(0, limit - 3)}...` : text
}

function prettyKind(kind) {
  return String(kind || 'event').replaceAll('_', ' ')
}

function prettyBytes(bytes) {
  const numeric = Number(bytes || 0)
  if (!Number.isFinite(numeric) || numeric <= 0) return ''
  return `${(numeric / (1024 * 1024)).toFixed(2)} MB`
}

function prettyJson(value) {
  if (value == null) return ''
  return JSON.stringify(value, null, 2)
}

function prettyCode(value) {
  return String(value || '').trim()
}

export function buildEventView(event) {
  const payload = event?.payload || {}
  const agent = event?.display_agent || event?.agent_id || ''
  const kind = event?.kind || 'event'
  const view = {
    kind,
    badge: payload?.message_type || payload?.relation_type || prettyKind(kind),
    badgeTone: KIND_BADGES[kind] || 'default',
    title: event?.title || 'Event',
    subtitle: event?.summary || '',
    lines: [],
    sections: [],
    progress: null,
    expandable: false,
  }

  switch (kind) {
    case 'decomposition_started':
      view.title = 'Director analyzing the research question'
      view.subtitle = shortText(payload.question, 220)
      break
    case 'decomposition_completed':
      view.title = 'Director drafted the research plan'
      view.lines.push(`Subproblems: ${payload.subproblems_count || 0}`)
      view.lines.push(`Open questions: ${payload.open_questions_count || 0}`)
      view.lines.push(`Assumptions: ${payload.key_assumptions_count || 0}`)
      if (payload.reasoning_summary) view.subtitle = shortText(payload.reasoning_summary, 220)
      break
    case 'decomposed_question':
      view.title = 'Director decomposed the research question'
      if (payload.reasoning_summary) view.subtitle = shortText(payload.reasoning_summary, 220)
      if (Array.isArray(payload.open_questions) && payload.open_questions.length) {
        view.sections.push({
          label: 'Open Questions',
          type: 'list',
          items: payload.open_questions.slice(0, 8),
        })
      }
      if (Array.isArray(payload.key_assumptions) && payload.key_assumptions.length) {
        view.sections.push({
          label: 'Key Assumptions',
          type: 'list',
          items: payload.key_assumptions.slice(0, 8),
        })
      }
      if (payload.archetype_reasoning) {
        view.sections.push({
          label: 'Archetype Rationale',
          type: 'text',
          content: payload.archetype_reasoning,
        })
      }
      break
    case 'archetype_design_started':
      view.title = 'Director designing archetypes'
      view.subtitle = `Target archetypes: ${payload.max_archetypes || 0}`
      break
    case 'archetype_design_completed':
      view.title = 'Director completed archetype design'
      view.subtitle = `Archetypes: ${payload.archetypes_count || 0}`
      if (Array.isArray(payload.archetype_names) && payload.archetype_names.length) {
        view.sections.push({
          label: 'Archetypes',
          type: 'list',
          items: payload.archetype_names,
        })
      }
      if (payload.reasoning_summary) {
        view.sections.push({
          label: 'Rationale',
          type: 'text',
          content: payload.reasoning_summary,
        })
      }
      break
    case 'download_source_progress':
      view.title = `${agent || 'Agent'} downloading arXiv PDF`
      view.subtitle = shortText(payload.title || payload.arxiv_id, 180)
      view.progress = Number(payload.progress || 0)
      if (payload.total_bytes) {
        view.lines.push(
          `${prettyBytes(payload.bytes_downloaded)} / ${prettyBytes(payload.total_bytes)}`
        )
      }
      if (payload.stage) {
        view.lines.push(`Stage: ${String(payload.stage).replaceAll('_', ' ')}`)
      }
      break
    case 'downloading_source':
      view.title = `${agent || 'Agent'} downloading arXiv PDF`
      view.subtitle = shortText(payload.title || payload.arxiv_id, 180)
      break
    case 'ingesting_source':
      view.title = `${agent || 'Agent'} ingesting arXiv PDF`
      view.subtitle = shortText(payload.title || payload.arxiv_id, 180)
      view.progress = Number(payload.progress || 100)
      break
    case 'ingested_search_source':
      view.title = `${agent || 'Agent'} ingested arXiv PDF`
      view.subtitle = shortText(payload.title || payload.source_id, 180)
      if (payload.file_path) {
        view.sections.push({
          label: 'Saved File',
          type: 'text',
          content: payload.file_path,
        })
      }
      break
    case 'search_source_already_ingested':
      view.title = `${agent || 'Agent'} reused an ingested arXiv paper`
      view.subtitle = shortText(payload.title || payload.arxiv_id, 180)
      break
    case 'arxiv_search_completed':
      view.title = 'arXiv search completed'
      view.subtitle = shortText(event.summary || payload.query, 180)
      if (Array.isArray(payload.titles) && payload.titles.length) {
        view.sections.push({
          label: 'Top Matches',
          type: 'list',
          items: payload.titles.slice(0, 6),
        })
      }
      break
    case 'source_ingested':
      view.title = 'Source ingested'
      view.subtitle = shortText(payload.title, 180)
      view.lines.push(`${payload.chunks_count || 0} chunks`)
      view.lines.push(`${payload.summaries_count || 0} summaries`)
      break
    case 'note_created':
      view.title = `${agent || 'Agent'} note`
      view.subtitle = shortText(payload.text, 200)
      break
    case 'assumption_created':
      view.title = `${agent || 'Agent'} assumption`
      view.subtitle = shortText(payload.text, 200)
      if (payload.basis) view.lines.push(`Basis: ${shortText(payload.basis, 160)}`)
      break
    case 'hypothesis_created':
      view.title = `${agent || 'Agent'} hypothesis`
      view.subtitle = shortText(payload.text, 200)
      if (payload.confidence != null) {
        view.lines.push(`Confidence: ${Math.round(Number(payload.confidence) * 100)}%`)
      }
      break
    case 'finding_created':
      view.title = `${agent || 'Agent'} finding`
      view.subtitle = shortText(payload.text, 200)
      if (payload.conclusion_type) {
        view.lines.push(`Conclusion: ${payload.conclusion_type}`)
      }
      break
    case 'relation_created':
      view.title = `${agent || 'Agent'} ${String(payload.relation_type || 'relation').toUpperCase()}`
      view.subtitle = payload.reasoning ? shortText(payload.reasoning, 200) : ''
      if (payload.source_preview) view.lines.push(`From: ${shortText(payload.source_preview, 180)}`)
      if (payload.target_preview) view.lines.push(`To: ${shortText(payload.target_preview, 180)}`)
      break
    case 'message_sent':
      view.title = `${agent || 'Agent'} sent ${String(payload.message_type || 'message').toUpperCase()}`
      view.subtitle = shortText(payload.text, 200)
      if (event.display_to_agent) {
        view.lines.push(`To: ${event.display_to_agent}`)
      }
      break
    case 'reviewing_hypothesis':
      view.title = `${agent || 'Agent'} reviewing a hypothesis`
      view.subtitle = shortText(payload.hypothesis_text, 200)
      break
    case 'reviewed_hypothesis':
      view.title = `${agent || 'Agent'} ${String(payload.verdict || 'reviewed').toUpperCase()} a hypothesis`
      view.subtitle = shortText(payload.hypothesis_text, 200)
      break
    case 'intra_cluster_review_started':
      view.title = 'Debate System started intra-cluster review'
      view.subtitle = `Planned reviews: ${payload.planned_reviews || 0}`
      if (Array.isArray(payload.review_plan_preview) && payload.review_plan_preview.length) {
        view.sections.push({
          label: 'Review Plan',
          type: 'list',
          items: payload.review_plan_preview.slice(0, 8).map((item) =>
            `${item.reviewer_name || item.reviewer_id || 'Reviewer'} reviewing ${item.peer_name || item.peer_id || 'peer'}: ${shortText(item.hypothesis_text, 120)}`
          ),
        })
      }
      break
    case 'inter_cluster_debate_started':
      view.title = 'Debate System started inter-cluster debate'
      view.subtitle = `Pairs: ${payload.pairs || 0}`
      if (Array.isArray(payload.pair_preview) && payload.pair_preview.length) {
        view.sections.push({
          label: 'Debate Pairs',
          type: 'list',
          items: payload.pair_preview.slice(0, 8).map((item) =>
            `${item.challenger_name || item.challenger_id || 'Challenger'} challenges ${item.target_owner_name || item.target_owner_id || 'peer'}: ${shortText(item.target_hypothesis_text, 120)}`
          ),
        })
      }
      break
    case 'counter_responses_started':
      view.title = 'Debate System started counter-responses'
      view.subtitle = `Challenged hypotheses: ${payload.challenged_hypotheses || 0}`
      if (Array.isArray(payload.challenged_hypothesis_preview) && payload.challenged_hypothesis_preview.length) {
        view.sections.push({
          label: 'Challenges',
          type: 'list',
          items: payload.challenged_hypothesis_preview.slice(0, 8).map((item) =>
            `${item.author_name || item.author_id || 'Author'} responding to ${item.reviewer_name || item.reviewer_id || 'reviewer'}: ${shortText(item.critique, 120)}`
          ),
        })
      }
      break
    case 'adjudication_started':
      view.title = 'Adjudicator started review'
      view.subtitle = `Targets: ${payload.targets || 0}`
      if (Array.isArray(payload.target_preview) && payload.target_preview.length) {
        view.sections.push({
          label: 'Contested Hypotheses',
          type: 'list',
          items: payload.target_preview.slice(0, 8).map((item) => shortText(item.target_text, 140)),
        })
      }
      break
    case 'experiment_started':
      view.title = 'Sandbox run started'
      view.subtitle = shortText(payload.expected_outcome || event.summary, 200)
      if (payload.input_data && Object.keys(payload.input_data).length) {
        view.sections.push({ label: 'Inputs', type: 'json', content: prettyJson(payload.input_data) })
      }
      if (payload.code_preview) {
        view.sections.push({ label: 'Code', type: 'code', content: prettyCode(payload.code_preview) })
      }
      break
    case 'experiment_completed':
      view.title = 'Sandbox run completed'
      view.subtitle = shortText(payload.stdout_preview || event.summary, 200)
      if (payload.input_data && Object.keys(payload.input_data).length) {
        view.sections.push({ label: 'Inputs', type: 'json', content: prettyJson(payload.input_data) })
      }
      if (payload.artifacts && Object.keys(payload.artifacts).length) {
        view.sections.push({ label: 'Results', type: 'json', content: prettyJson(payload.artifacts) })
      }
      if (payload.stderr_preview) {
        view.sections.push({ label: 'Stderr', type: 'text', content: payload.stderr_preview })
      }
      break
    case 'experiment_failed':
      view.title = 'Sandbox run failed'
      view.subtitle = shortText(payload.error || event.summary, 200)
      if (payload.input_data && Object.keys(payload.input_data).length) {
        view.sections.push({ label: 'Inputs', type: 'json', content: prettyJson(payload.input_data) })
      }
      if (payload.code_preview) {
        view.sections.push({ label: 'Code', type: 'code', content: prettyCode(payload.code_preview) })
      }
      if (payload.stdout_preview) {
        view.sections.push({ label: 'Output', type: 'text', content: payload.stdout_preview })
      }
      break
    case 'iteration_completed':
      view.title = `Iteration ${payload.iteration ?? ''} complete`
      view.subtitle = shortText(payload.reasoning || event.summary, 220)
      if (Array.isArray(payload.directives) && payload.directives.length) {
        view.sections.push({
          label: 'Directives',
          type: 'list',
          items: payload.directives,
        })
      }
      break
    case 'error':
      view.title = event.title || 'Error'
      view.subtitle = shortText(event.summary || payload.error, 220)
      break
    default:
      view.title = event?.title || 'Event'
      view.subtitle = shortText(event?.summary, 220)
      break
  }

  view.expandable =
    view.sections.length > 0 ||
    (event?.payload && Object.keys(event.payload).length > 0) ||
    (event?.refs && Object.keys(event.refs).length > 0) ||
    view.lines.length > 2

  return view
}
