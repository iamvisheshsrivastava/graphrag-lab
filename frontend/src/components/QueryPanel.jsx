import { useState } from 'react'
import { Send, Loader, Lightbulb, Route } from 'lucide-react'
import { queryGraph } from '../lib/api'

const EXAMPLE_QUERIES = [
  'Which requirements involve ultrasonic sensors?',
  'What are the safety requirements for ASIL-B compliance?',
  'Show all dependencies of REQ-003',
  'Which requirements address pedestrian detection?',
  'What sensor redundancy is required for parking functions?',
]

export default function QueryPanel({ graph, onHighlight }) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleQuery() {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    try {
      const res = await queryGraph(query)
      setResult(res)
      if (onHighlight) onHighlight(res.traversal_path || [])
    } catch (e) {
      // Offline mock
      const mock = buildMockResult(query, graph)
      setResult(mock)
      if (onHighlight) onHighlight(mock.traversal_path)
      setError('Backend offline — showing deterministic mock result')
    }
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Input */}
      <div className="card space-y-3">
        <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">
          Natural Language Query
        </label>
        <div className="flex gap-2">
          <input
            className="input flex-1"
            placeholder="e.g. Which requirements depend on ultrasonic sensors?"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleQuery()}
          />
          <button onClick={handleQuery} disabled={!query.trim() || loading} className="btn-primary flex items-center gap-1.5 shrink-0">
            {loading ? <Loader size={13} className="animate-spin" /> : <Send size={13} />}
            Query
          </button>
        </div>

        {/* Example queries */}
        <div>
          <p className="text-[10px] text-slate-500 mb-1.5 flex items-center gap-1">
            <Lightbulb size={10} /> Example queries
          </p>
          <div className="flex flex-wrap gap-1.5">
            {EXAMPLE_QUERIES.map(q => (
              <button key={q} onClick={() => setQuery(q)}
                className="text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 px-2 py-1 rounded border border-slate-700/50 transition-colors">
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="text-xs text-amber-400 px-1">{error}</p>}

      {/* Result */}
      {result && (
        <div className="flex-1 overflow-y-auto space-y-3">
          {/* Answer */}
          <div className="card space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Answer</p>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-slate-500">Confidence:</span>
                <div className="w-20 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-brand-500 rounded-full transition-all"
                    style={{ width: `${(result.confidence * 100).toFixed(0)}%` }} />
                </div>
                <span className="text-[10px] text-slate-400">{(result.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
            <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{result.answer}</p>
          </div>

          {/* Traversal path */}
          {result.traversal_path?.length > 0 && (
            <div className="card space-y-2">
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider flex items-center gap-1">
                <Route size={11} /> Graph Traversal Path
              </p>
              <div className="flex flex-wrap gap-1.5">
                {result.traversal_path.slice(0, 12).map((node, i) => (
                  <span key={i} className="flex items-center gap-1">
                    <span className="font-mono text-[11px] bg-slate-800 text-brand-400 px-1.5 py-0.5 rounded border border-brand-500/20">
                      {node}
                    </span>
                    {i < Math.min(result.traversal_path.length - 1, 11) && (
                      <span className="text-slate-600 text-xs">→</span>
                    )}
                  </span>
                ))}
                {result.traversal_path.length > 12 && (
                  <span className="text-[10px] text-slate-500">+{result.traversal_path.length - 12} more</span>
                )}
              </div>
            </div>
          )}

          {/* Relevant nodes */}
          {result.relevant_nodes?.length > 0 && (
            <div className="card space-y-2">
              <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Relevant Nodes</p>
              <div className="space-y-1.5">
                {result.relevant_nodes.map(node => (
                  <div key={node.id} className="flex items-start gap-2 py-1">
                    <span className="font-mono text-[11px] text-brand-400 bg-brand-500/10 px-1.5 py-0.5 rounded shrink-0">
                      {node.id}
                    </span>
                    <span className="text-[11px] text-slate-400 capitalize">{node.type?.replace('_', ' ')}</span>
                    {node.properties?.text && (
                      <span className="text-[11px] text-slate-500 truncate">{node.properties.text.slice(0, 80)}…</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function buildMockResult(query, graph) {
  const lower = query.toLowerCase()
  const allNodes = graph?.nodes || []
  const relevant = allNodes.filter(n =>
    lower.split(' ').some(w => w.length > 3 && (n.id.toLowerCase().includes(w) || JSON.stringify(n.properties).toLowerCase().includes(w)))
  ).slice(0, 5)

  return {
    query,
    answer: relevant.length
      ? `Found ${relevant.length} relevant graph node(s):\n${relevant.map(n => `• ${n.id} (${n.type})`).join('\n')}\n\nConnect an OpenAI API key for full LLM-generated, traceable answers.`
      : `No matching nodes found for "${query}". Try broader terms or load the sample dataset first.`,
    relevant_nodes: relevant,
    traversal_path: relevant.map(n => n.id),
    confidence: relevant.length ? 0.6 : 0.1,
    sources: relevant.map(n => n.id),
  }
}
