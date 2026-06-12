import { useState, useEffect } from 'react'
import { Play, Database, Zap, AlertCircle, CheckCircle } from 'lucide-react'
import { runCypher, getNeo4jStatus } from '../lib/api'
import clsx from 'clsx'

const EXAMPLE_QUERIES = [
  {
    label: 'All requirements',
    query: 'MATCH (r:Requirement) RETURN r.id AS id, r.req_type AS type, r.sae_level AS sae, r.text AS text ORDER BY r.id',
  },
  {
    label: 'Requirements → Entities',
    query: 'MATCH (r:Requirement)-[rel]->(e:Entity) RETURN r.id AS requirement, type(rel) AS relation, e.id AS entity, e.entity_type AS entity_type ORDER BY r.id',
  },
  {
    label: 'Safety requirements',
    query: "MATCH (r:Requirement {req_type: 'safety'}) RETURN r.id AS id, r.text AS text",
  },
  {
    label: 'Dependency chains',
    query: 'MATCH p=(r:Requirement)-[:DEPENDS_ON*1..3]->(r2:Requirement) RETURN r.id AS from, r2.id AS to, length(p) AS depth ORDER BY depth',
  },
  {
    label: 'Node count by label',
    query: 'MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC',
  },
  {
    label: 'ASIL entities',
    query: "MATCH (e:Entity) WHERE e.id CONTAINS 'ASIL' RETURN e.id, e.label, e.entity_type",
  },
]

export default function CypherConsole() {
  const [query, setQuery] = useState(EXAMPLE_QUERIES[0].query)
  const [result, setResult] = useState(null)
  const [error, setError]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [neo4j, setNeo4j]   = useState(null)

  useEffect(() => {
    getNeo4jStatus()
      .then(s => setNeo4j(s))
      .catch(() => setNeo4j({ connected: false, reason: 'unreachable' }))
  }, [])

  async function execute() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await runCypher(query)
      setResult(data)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Query failed')
    }
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-brand-400" />
          <h2 className="text-sm font-semibold text-white">Cypher Console</h2>
          <span className="text-[10px] text-slate-500">Neo4j AuraDB</span>
        </div>
        {neo4j && (
          <span className={clsx(
            'flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full border',
            neo4j.connected
              ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
              : 'text-red-400 border-red-500/30 bg-red-500/10'
          )}>
            {neo4j.connected
              ? <><CheckCircle size={10} /> Connected · {neo4j.node_count} nodes</>
              : <><AlertCircle size={10} /> {neo4j.reason}</>}
          </span>
        )}
      </div>

      {/* Example query chips */}
      <div className="flex flex-wrap gap-1.5">
        {EXAMPLE_QUERIES.map(ex => (
          <button
            key={ex.label}
            onClick={() => setQuery(ex.query)}
            className="text-[10px] px-2 py-1 rounded bg-slate-700/60 text-slate-400 border border-slate-600/40 hover:border-brand-500/50 hover:text-brand-300 transition-colors"
          >
            {ex.label}
          </button>
        ))}
      </div>

      {/* Editor */}
      <div className="relative">
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) execute() }}
          rows={5}
          spellCheck={false}
          className="w-full bg-slate-900 border border-slate-700/60 rounded-lg px-4 py-3 text-sm font-mono text-slate-200 focus:outline-none focus:border-brand-500/60 resize-none"
          placeholder="MATCH (n) RETURN n LIMIT 25"
        />
        <span className="absolute bottom-2.5 right-3 text-[10px] text-slate-600">Ctrl+Enter to run</span>
      </div>

      <button
        onClick={execute}
        disabled={loading || !query.trim()}
        className="btn-primary flex items-center gap-2 self-start"
      >
        <Play size={13} />
        {loading ? 'Running…' : 'Run Query'}
        {result && !loading && (
          <span className="ml-1 text-[10px] opacity-70">{result.row_count} rows</span>
        )}
      </button>

      {/* Error */}
      {error && (
        <div className="card border-red-500/30 bg-red-500/10 text-red-300 text-sm flex items-start gap-2">
          <AlertCircle size={14} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Results table */}
      {result && result.row_count > 0 && (
        <div className="flex-1 overflow-auto rounded-lg border border-slate-700/50">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-800/80 border-b border-slate-700/50">
                {result.columns.map(col => (
                  <th key={col} className="px-3 py-2 text-left text-slate-400 font-medium whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, i) => (
                <tr key={i} className={clsx('border-b border-slate-800/60', i % 2 === 0 ? 'bg-slate-900/40' : 'bg-slate-800/20')}>
                  {result.columns.map(col => (
                    <td key={col} className="px-3 py-1.5 text-slate-300 max-w-xs truncate">
                      {typeof row[col] === 'object'
                        ? JSON.stringify(row[col])
                        : String(row[col] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result && result.row_count === 0 && (
        <div className="card text-center text-slate-500 text-sm py-8">
          Query returned 0 rows — build the knowledge graph first or adjust your query.
        </div>
      )}
    </div>
  )
}
