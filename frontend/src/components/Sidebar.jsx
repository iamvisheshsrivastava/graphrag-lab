import { GitBranch, Search, CheckSquare, List, Activity, ChevronRight, Database } from 'lucide-react'
import clsx from 'clsx'

const NAV = [
  { id: 'requirements', label: 'Requirements',   icon: List },
  { id: 'graph',        label: 'Knowledge Graph', icon: GitBranch },
  { id: 'query',        label: 'GraphRAG Query',  icon: Search },
  { id: 'verify',       label: 'Verification',    icon: CheckSquare },
  { id: 'traceability', label: 'Traceability',    icon: Activity },
  { id: 'cypher',       label: 'Cypher Console',  icon: Database },
]

export default function Sidebar({ active, onNav }) {
  return (
    <aside className="w-56 shrink-0 bg-surface-900 border-r border-slate-700/50 flex flex-col">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-brand-600 rounded-lg flex items-center justify-center">
            <GitBranch size={14} className="text-white" />
          </div>
          <div>
            <p className="text-xs font-bold text-white leading-tight">GraphRAG</p>
            <p className="text-[10px] text-slate-400 leading-tight">Parking · ADAS</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onNav(id)}
            className={clsx(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group',
              active === id
                ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/40'
            )}
          >
            <Icon size={15} />
            <span className="flex-1 text-left">{label}</span>
            {active === id && <ChevronRight size={12} className="opacity-60" />}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-700/50">
        <p className="text-[10px] text-slate-500 leading-relaxed">
          GraphRAG · ADAS Requirements<br />
          ISO 26262 · SAE J3016
        </p>
      </div>
    </aside>
  )
}
