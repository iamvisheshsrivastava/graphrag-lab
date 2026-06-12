import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import { ZoomIn, ZoomOut, Maximize2, RotateCcw } from 'lucide-react'

const NODE_COLORS = {
  requirement:      '#6366f1',
  sensor:           '#10b981',
  function:         '#f59e0b',
  concept:          '#8b5cf6',
  safety_level:     '#ef4444',
  actor:            '#06b6d4',
  requirement_type: '#ec4899',
  default:          '#64748b',
}

const CYTO_STYLE = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      'label': 'data(label)',
      'color': '#e2e8f0',
      'font-size': '10px',
      'font-family': 'Inter, sans-serif',
      'text-valign': 'bottom',
      'text-margin-y': '4px',
      'text-outline-color': '#13131f',
      'text-outline-width': '2px',
      'width': 'data(size)',
      'height': 'data(size)',
      'border-width': 2,
      'border-color': 'data(borderColor)',
      'border-opacity': 0.6,
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 3,
      'border-color': '#ffffff',
      'border-opacity': 1,
    },
  },
  {
    selector: 'edge',
    style: {
      'width': 1.5,
      'line-color': '#475569',
      'target-arrow-color': '#475569',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'label': 'data(label)',
      'font-size': '8px',
      'color': '#94a3b8',
      'text-outline-color': '#13131f',
      'text-outline-width': '1.5px',
      'text-rotation': 'autorotate',
    },
  },
  {
    selector: 'edge[relation="depends_on"]',
    style: { 'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b', 'width': 2 },
  },
  {
    selector: 'edge[relation="conflicts_with"]',
    style: { 'line-color': '#ef4444', 'target-arrow-color': '#ef4444', 'line-style': 'dashed' },
  },
  {
    selector: 'edge[relation="derives_from"]',
    style: { 'line-color': '#a78bfa', 'target-arrow-color': '#a78bfa' },
  },
  {
    selector: 'edge[relation="mentions"]',
    style: { 'line-color': '#334155', 'target-arrow-color': '#334155' },
  },
]

function toCytoElements(graph) {
  if (!graph) return []

  const elements = []
  const nodeIds = new Set(graph.nodes.map(n => n.id))

  for (const node of graph.nodes) {
    const color = NODE_COLORS[node.type] || NODE_COLORS.default
    elements.push({
      data: {
        id: node.id,
        label: node.label.length > 20 ? node.label.slice(0, 18) + '…' : node.label,
        fullLabel: node.label,
        type: node.type,
        color,
        borderColor: color,
        size: node.type === 'requirement' ? 28 : 20,
        properties: node.properties,
      },
    })
  }

  for (const edge of graph.edges) {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) continue
    elements.push({
      data: {
        id: `${edge.source}--${edge.relation}--${edge.target}`,
        source: edge.source,
        target: edge.target,
        relation: edge.relation,
        label: edge.relation.replace(/_/g, ' '),
      },
    })
  }

  return elements
}

export default function GraphViewer({ graph, highlightNodes = [] }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    if (!containerRef.current || !graph) return

    if (cyRef.current) cyRef.current.destroy()

    const cy = cytoscape({
      container: containerRef.current,
      elements: toCytoElements(graph),
      style: CYTO_STYLE,
      layout: { name: 'cose', animate: true, padding: 40, nodeRepulsion: 8000, idealEdgeLength: 80 },
      wheelSensitivity: 0.3,
    })

    cy.on('tap', 'node', evt => {
      const d = evt.target.data()
      setSelected({ id: d.id, type: d.type, properties: d.properties, fullLabel: d.fullLabel })
    })
    cy.on('tap', evt => {
      if (evt.target === cy) setSelected(null)
    })

    cyRef.current = cy
    return () => cy.destroy()
  }, [graph])

  // Highlight traversal nodes
  useEffect(() => {
    if (!cyRef.current || !highlightNodes.length) return
    cyRef.current.nodes().style({ opacity: 0.3 })
    highlightNodes.forEach(id => {
      const node = cyRef.current.getElementById(id)
      if (node.length) node.style({ opacity: 1, 'border-width': 3, 'border-color': '#fbbf24' })
    })
  }, [highlightNodes])

  if (!graph) {
    return (
      <div className="card h-full flex items-center justify-center text-slate-500">
        <p className="text-sm">Build a graph first — load requirements and click "Build Knowledge Graph"</p>
      </div>
    )
  }

  return (
    <div className="flex h-full gap-3">
      {/* Graph canvas */}
      <div className="flex-1 card relative p-0 overflow-hidden">
        <div ref={containerRef} className="cy-container w-full h-full" />

        {/* Zoom controls */}
        <div className="absolute top-3 right-3 flex flex-col gap-1">
          {[
            { icon: ZoomIn,     action: () => cyRef.current?.zoom(cyRef.current.zoom() * 1.2) },
            { icon: ZoomOut,    action: () => cyRef.current?.zoom(cyRef.current.zoom() * 0.8) },
            { icon: Maximize2,  action: () => cyRef.current?.fit(undefined, 30) },
            { icon: RotateCcw,  action: () => cyRef.current?.layout({ name: 'cose', animate: true }).run() },
          ].map(({ icon: Icon, action }, i) => (
            <button key={i} onClick={action}
              className="w-7 h-7 bg-surface-900/90 border border-slate-700/70 rounded flex items-center justify-center text-slate-400 hover:text-slate-200 hover:border-slate-500 transition-colors">
              <Icon size={12} />
            </button>
          ))}
        </div>

        {/* Legend */}
        <div className="absolute bottom-3 left-3 card p-2 text-[10px] space-y-1 opacity-80">
          {Object.entries(NODE_COLORS).filter(([k]) => k !== 'default').map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
              <span className="text-slate-400 capitalize">{type.replace('_', ' ')}</span>
            </div>
          ))}
        </div>

        {/* Stats */}
        <div className="absolute top-3 left-3 flex gap-2">
          <span className="badge bg-surface-900/90 border border-slate-700/60 text-slate-400">
            {graph.nodes.length} nodes
          </span>
          <span className="badge bg-surface-900/90 border border-slate-700/60 text-slate-400">
            {graph.edges.length} edges
          </span>
          {graph.metadata?.is_dag && (
            <span className="badge bg-emerald-900/50 border border-emerald-700/50 text-emerald-400">DAG ✓</span>
          )}
        </div>
      </div>

      {/* Node detail panel */}
      {selected && (
        <div className="w-56 shrink-0 card space-y-3 overflow-y-auto">
          <div>
            <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Selected Node</p>
            <p className="font-mono font-bold text-brand-400 text-sm">{selected.id}</p>
            <span className="badge mt-1" style={{ background: (NODE_COLORS[selected.type] || '#475569') + '33', color: NODE_COLORS[selected.type] || '#94a3b8', border: `1px solid ${(NODE_COLORS[selected.type] || '#475569')}66` }}>
              {selected.type?.replace('_', ' ')}
            </span>
          </div>
          {selected.properties && Object.entries(selected.properties).map(([k, v]) => (
            <div key={k}>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">{k}</p>
              <p className="text-xs text-slate-300 break-words">
                {typeof v === 'object' ? JSON.stringify(v) : String(v)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
