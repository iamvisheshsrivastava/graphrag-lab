import { useState } from 'react'
import { Activity, ArrowRight, ArrowLeft, GitMerge } from 'lucide-react'
import { getTraceability } from '../lib/api'
import clsx from 'clsx'

export default function TraceabilityPanel({ graph, requirements }) {
  const [selected, setSelected] = useState('')
  const [links, setLinks] = useState([])
  const [loading, setLoading] = useState(false)

  const reqIds = requirements?.map(r => r.id) || []

  async function fetchLinks(id) {
    setSelected(id)
    setLoading(true)
    try {
      const res = await getTraceability(id)
      setLinks(res)
    } catch {
      setLinks(buildMockLinks(id, graph))
    }
    setLoading(false)
  }

  const upstream = links.filter(l => l.target_id === selected)
  const downstream = links.filter(l => l.source_id === selected)

  return (
    <div className="flex h-full gap-4">
      {/* Requirement selector */}
      <div className="w-44 shrink-0 space-y-1 overflow-y-auto">
        <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2 px-1">Select Requirement</p>
        {reqIds.length === 0 ? (
          <p className="text-xs text-slate-500 px-1">Load requirements first</p>
        ) : reqIds.map(id => (
          <button key={id} onClick={() => fetchLinks(id)}
            className={clsx(
              'w-full text-left font-mono text-xs px-3 py-2 rounded-lg transition-colors',
              selected === id
                ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/40'
            )}>
            {id}
          </button>
        ))}
      </div>

      {/* Traceability detail */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {!selected ? (
          <div className="card flex flex-col items-center justify-center h-64 text-slate-500">
            <Activity size={28} className="mb-3 opacity-30" />
            <p className="text-sm">Select a requirement to explore its trace links</p>
          </div>
        ) : (
          <>
            <div className="card">
              <div className="flex items-center gap-2 mb-1">
                <GitMerge size={14} className="text-brand-400" />
                <span className="font-mono font-bold text-brand-400">{selected}</span>
                <span className="text-xs text-slate-400 ml-auto">
                  {upstream.length} upstream · {downstream.length} downstream
                </span>
              </div>
            </div>

            {/* Upstream */}
            {upstream.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center gap-1">
                  <ArrowLeft size={11} /> Upstream (depends on me)
                </p>
                {upstream.map((l, i) => <LinkCard key={i} link={l} direction="upstream" />)}
              </div>
            )}

            {/* Downstream */}
            {downstream.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center gap-1">
                  <ArrowRight size={11} /> Downstream (I depend on)
                </p>
                {downstream.map((l, i) => <LinkCard key={i} link={l} direction="downstream" />)}
              </div>
            )}

            {links.length === 0 && !loading && (
              <div className="card text-center text-slate-500 py-8">
                <p className="text-sm">No traceability links found for {selected}</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function LinkCard({ link, direction }) {
  const REL_COLORS = {
    depends_on:    'text-amber-400 bg-amber-500/10 border-amber-500/30',
    mentions:      'text-slate-400 bg-slate-500/10 border-slate-500/30',
    derives_from:  'text-purple-400 bg-purple-500/10 border-purple-500/30',
    implements:    'text-blue-400 bg-blue-500/10 border-blue-500/30',
    conflicts_with:'text-red-400 bg-red-500/10 border-red-500/30',
  }
  const cls = REL_COLORS[link.link_type] || REL_COLORS.mentions

  return (
    <div className="card flex items-center gap-3">
      <span className="font-mono text-xs text-slate-400">{link.source_id}</span>
      <span className={clsx('badge border text-[10px]', cls)}>{link.link_type.replace(/_/g, ' ')}</span>
      <span className="font-mono text-xs text-slate-400">{link.target_id}</span>
      {link.rationale && <span className="text-[10px] text-slate-500 ml-auto">{link.rationale}</span>}
    </div>
  )
}

function buildMockLinks(reqId, graph) {
  if (!graph) return []
  const links = []
  for (const edge of graph.edges || []) {
    if (edge.source === reqId) {
      links.push({ source_id: edge.source, target_id: edge.target, link_type: edge.relation, rationale: 'Downstream link' })
    }
    if (edge.target === reqId) {
      links.push({ source_id: edge.source, target_id: edge.target, link_type: edge.relation, rationale: 'Upstream link' })
    }
  }
  return links
}
