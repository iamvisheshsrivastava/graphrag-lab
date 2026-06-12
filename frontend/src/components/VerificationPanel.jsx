import { useState } from 'react'
import { ShieldCheck, AlertTriangle, XCircle, CheckCircle, Loader } from 'lucide-react'
import { verifyAll } from '../lib/api'
import clsx from 'clsx'

const STATUS_CONFIG = {
  verified:   { icon: CheckCircle,   color: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/30' },
  incomplete: { icon: AlertTriangle, color: 'text-amber-400',   bg: 'bg-amber-500/10 border-amber-500/30' },
  conflict:   { icon: XCircle,       color: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/30' },
  ambiguous:  { icon: AlertTriangle, color: 'text-orange-400',  bg: 'bg-orange-500/10 border-orange-500/30' },
}

export default function VerificationPanel({ requirements }) {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  async function runVerification() {
    setLoading(true)
    try {
      const res = await verifyAll()
      setResults(res)
    } catch {
      // Offline mock
      setResults(buildMockVerification(requirements))
    }
    setLoading(false)
  }

  const summary = results.reduce((acc, r) => {
    acc[r.status] = (acc[r.status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex items-center gap-3">
        <button onClick={runVerification} disabled={loading || !requirements?.length}
          className="btn-primary flex items-center gap-1.5">
          {loading ? <Loader size={13} className="animate-spin" /> : <ShieldCheck size={13} />}
          Run Verification
        </button>
        {results.length > 0 && (
          <div className="flex gap-2">
            {Object.entries(summary).map(([status, count]) => {
              const cfg = STATUS_CONFIG[status]
              const Icon = cfg?.icon || ShieldCheck
              return (
                <span key={status} className={clsx('badge border', cfg?.bg)}>
                  <Icon size={10} className={clsx('mr-1', cfg?.color)} />
                  <span className={cfg?.color}>{count} {status}</span>
                </span>
              )
            })}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto space-y-3">
        {results.length === 0 ? (
          <div className="card flex flex-col items-center justify-center py-16 text-slate-500">
            <ShieldCheck size={32} className="mb-3 opacity-30" />
            <p className="text-sm">Run verification to check requirements against ontology rules</p>
            <p className="text-xs mt-1 opacity-70">Checks ISO 26262, SAE L2, and consistency constraints</p>
          </div>
        ) : results.map(res => {
          const cfg = STATUS_CONFIG[res.status] || STATUS_CONFIG.incomplete
          const Icon = cfg.icon
          return (
            <div key={res.requirement_id} className={clsx('card border', cfg.bg)}>
              <div className="flex items-center gap-2 mb-2">
                <Icon size={14} className={cfg.color} />
                <span className="font-mono text-sm font-bold text-slate-200">{res.requirement_id}</span>
                <span className={clsx('badge capitalize text-[11px]', cfg.color)}>{res.status}</span>
              </div>

              {res.issues.length > 0 && (
                <div className="space-y-1 mb-2">
                  {res.issues.map((issue, i) => (
                    <p key={i} className="text-xs text-slate-300 flex gap-1.5">
                      <span className="text-red-400 shrink-0">✗</span> {issue}
                    </p>
                  ))}
                </div>
              )}

              {res.suggestions.length > 0 && (
                <div className="space-y-1 mt-2 pt-2 border-t border-slate-700/40">
                  {res.suggestions.map((s, i) => (
                    <p key={i} className="text-xs text-slate-400 flex gap-1.5">
                      <span className="text-brand-400 shrink-0">→</span> {s}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function buildMockVerification(reqs) {
  if (!reqs?.length) return []
  return reqs.map(req => {
    const issues = []
    const suggestions = []
    const text = req.text?.toLowerCase() || ''

    if (req.sae_level === 'L2' && !text.includes('monitor')) {
      issues.push('SAE L2 requirement missing driver monitoring obligation')
      suggestions.push("Add: 'The driver shall continuously monitor the environment'")
    }
    if (req.type === 'safety' && !text.includes('asil') && !text.includes('iso')) {
      issues.push('Safety requirement lacks ISO 26262 / ASIL reference')
      suggestions.push('Specify the required ASIL level')
    }
    if (req.type === 'performance' && !/\d/.test(req.text)) {
      issues.push('Performance requirement has no quantitative threshold')
      suggestions.push('Add measurable acceptance criterion')
    }

    return {
      requirement_id: req.id,
      status: issues.length === 0 ? 'verified' : issues.length > 1 ? 'conflict' : 'incomplete',
      issues,
      suggestions,
    }
  })
}
