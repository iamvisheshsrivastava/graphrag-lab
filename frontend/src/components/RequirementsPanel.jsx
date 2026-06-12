import { useState, useEffect, useRef } from 'react'
import { Plus, Upload, Play, Trash2, Tag, Wifi, FileUp, AlertTriangle } from 'lucide-react'
import { fetchSampleRequirements, addRequirements, buildGraph, wakeBackend } from '../lib/api'
import clsx from 'clsx'

const TYPE_COLORS = {
  functional:     'bg-blue-500/20 text-blue-300 border-blue-500/30',
  safety:         'bg-red-500/20 text-red-300 border-red-500/30',
  performance:    'bg-amber-500/20 text-amber-300 border-amber-500/30',
  non_functional: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  interface:      'bg-green-500/20 text-green-300 border-green-500/30',
}

// ─── File parsers ────────────────────────────────────────────────────────────
function parseJSON(text) {
  const data = JSON.parse(text)
  return Array.isArray(data) ? data : data.requirements ?? []
}

function parseCSV(text) {
  const lines = text.trim().split('\n')
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
  return lines.slice(1).map((line, i) => {
    const vals = line.match(/(".*?"|[^,]+)/g) ?? []
    const obj = {}
    headers.forEach((h, j) => { obj[h] = (vals[j] ?? '').replace(/^"|"$/g, '').trim() })
    return {
      id:        obj.id        || `UPLOAD-${String(i + 1).padStart(3, '0')}`,
      text:      obj.text      || obj.description || obj.requirement || '',
      type:      obj.type      || 'functional',
      sae_level: obj.sae_level || obj.sae || 'L2',
      domain:    obj.domain    || 'parking',
      tags:      obj.tags ? obj.tags.split(';').map(t => t.trim()) : [],
    }
  }).filter(r => r.text)
}

export default function RequirementsPanel({ onGraphBuilt }) {
  const [reqs, setReqs] = useState([])
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [backendAwake, setBackendAwake] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const fileRef = useRef(null)

  // Silently wake the backend as soon as the panel mounts
  useEffect(() => {
    wakeBackend().then(() => setBackendAwake(true))
  }, [])

  function handleFileUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploadError(null)
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const text = ev.target.result
        let parsed
        if (file.name.endsWith('.json')) parsed = parseJSON(text)
        else if (file.name.endsWith('.csv')) parsed = parseCSV(text)
        else throw new Error('Only .json and .csv files are supported')
        if (!parsed.length) throw new Error('No valid requirements found in file')
        setReqs(parsed)
        setStatus(`Loaded ${parsed.length} requirements from ${file.name}`)
      } catch (err) {
        setUploadError(err.message)
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  async function loadSample() {
    setLoading(true)
    if (!backendAwake) {
      setStatus('Waking up backend (first load ~30s)…')
    } else {
      setStatus('Loading sample requirements…')
    }
    try {
      const data = await fetchSampleRequirements()
      setReqs(data)
      setBackendAwake(true)
      setStatus(`Loaded ${data.length} requirements`)
    } catch {
      setStatus('Backend offline — showing mock data')
      setReqs(MOCK_REQS)
    }
    setLoading(false)
  }

  async function handleBuildGraph() {
    if (!reqs.length) return
    setLoading(true)
    setStatus('Building knowledge graph…')
    try {
      await addRequirements(reqs)
      const graph = await buildGraph(reqs)
      onGraphBuilt(graph, reqs)
      setStatus(`Graph built: ${graph.nodes.length} nodes, ${graph.edges.length} edges`)
    } catch {
      setStatus('Using offline graph — connect backend to persist')
      onGraphBuilt(buildMockGraph(reqs), reqs)
    }
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={loadSample} disabled={loading} className="btn-primary flex items-center gap-1.5">
          <Upload size={13} /> Load Sample Dataset
        </button>
        {/* File upload */}
        <button
          onClick={() => fileRef.current?.click()}
          disabled={loading}
          className="btn-ghost flex items-center gap-1.5 border border-slate-600/60 hover:border-brand-500/50"
          title="Upload your own .json or .csv requirements file"
        >
          <FileUp size={13} /> Upload File
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".json,.csv"
          className="hidden"
          onChange={handleFileUpload}
        />
        <button
          onClick={handleBuildGraph}
          disabled={!reqs.length || loading}
          className="btn-primary flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700"
        >
          <Play size={13} /> Build Knowledge Graph
        </button>
        {reqs.length > 0 && (
          <button onClick={() => { setReqs([]); setUploadError(null) }} className="btn-ghost flex items-center gap-1.5">
            <Trash2 size={12} /> Clear
          </button>
        )}
        <span className="ml-auto flex items-center gap-2">
          {status && <span className="text-xs text-slate-400">{status}</span>}
          <span className={clsx('flex items-center gap-1 text-[10px]', backendAwake ? 'text-emerald-400' : 'text-slate-500')}>
            <Wifi size={10} /> {backendAwake ? 'API ready' : 'connecting…'}
          </span>
        </span>
      </div>

      {/* Upload error */}
      {uploadError && (
        <div className="flex items-center gap-2 text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-2">
          <AlertTriangle size={12} className="shrink-0" />
          {uploadError}
          <span className="ml-1 text-slate-500">— Expected: JSON array or CSV with columns: id, text, type, sae_level</span>
        </div>
      )}

      {/* Stats */}
      {reqs.length > 0 && (
        <div className="grid grid-cols-5 gap-2">
          {Object.entries(TYPE_COLORS).map(([type, cls]) => {
            const count = reqs.filter(r => r.type === type).length
            return (
              <div key={type} className={clsx('card text-center py-2', cls)}>
                <p className="text-lg font-bold">{count}</p>
                <p className="text-[10px] capitalize opacity-80">{type.replace('_', ' ')}</p>
              </div>
            )
          })}
        </div>
      )}

      {/* Requirements list */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {reqs.length === 0 ? (
          <div className="card flex flex-col items-center justify-center py-16 text-slate-500">
            <Plus size={32} className="mb-3 opacity-30" />
            <p className="text-sm">Load sample requirements or add your own</p>
          </div>
        ) : (
          reqs.map(req => (
            <div key={req.id} className="card hover:border-slate-600/70 transition-colors group">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-brand-400">{req.id}</span>
                  <span className={clsx('badge border', TYPE_COLORS[req.type] || 'bg-slate-700 text-slate-300')}>
                    {req.type?.replace('_', ' ')}
                  </span>
                  <span className="badge bg-slate-700/60 text-slate-400 border border-slate-600/50">
                    SAE {req.sae_level}
                  </span>
                </div>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">{req.text}</p>
              {req.tags?.length > 0 && (
                <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                  <Tag size={10} className="text-slate-500" />
                  {req.tags.map(tag => (
                    <span key={tag} className="text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ─── Mock data for offline mode ───────────────────────────────────────────────
const MOCK_REQS = [
  { id: 'REQ-001', text: 'The APA system shall detect parking spaces using ultrasonic sensors with range ≥ 4.5m.', type: 'functional', sae_level: 'L2', tags: ['detection', 'ultrasonic'] },
  { id: 'REQ-002', text: 'The driver shall continuously monitor the vehicle during APA and be ready to take over.', type: 'safety', sae_level: 'L2', tags: ['driver monitoring', 'takeover'] },
  { id: 'REQ-003', text: 'Trajectory computation shall complete within 200ms of slot detection. REQ-001 must be active.', type: 'performance', sae_level: 'L2', tags: ['latency', 'trajectory'] },
  { id: 'REQ-004', text: 'RPA software shall conform to ISO 26262 ASIL-B for safety-relevant components.', type: 'safety', sae_level: 'L2', tags: ['ASIL-B', 'ISO26262'] },
  { id: 'REQ-005', text: 'Camera360 surround-view shall deliver 1280×720 @ 30fps for obstacle detection.', type: 'functional', sae_level: 'L2', tags: ['camera', 'surround view'] },
]

function buildMockGraph(reqs) {
  const nodes = reqs.map(r => ({ id: r.id, label: r.id, type: 'requirement', properties: { text: r.text } }))
  nodes.push(
    { id: 'UltrasonicSensor', label: 'Ultrasonic Sensor', type: 'sensor', properties: {} },
    { id: 'Camera360', label: 'Camera 360°', type: 'sensor', properties: {} },
    { id: 'ISO26262', label: 'ISO 26262', type: 'concept', properties: {} },
  )
  const edges = [
    { source: 'REQ-001', target: 'UltrasonicSensor', relation: 'mentions' },
    { source: 'REQ-003', target: 'REQ-001', relation: 'depends_on' },
    { source: 'REQ-004', target: 'ISO26262', relation: 'derives_from' },
    { source: 'REQ-005', target: 'Camera360', relation: 'mentions' },
  ]
  return { nodes, edges, metadata: { num_requirements: reqs.length, is_dag: true } }
}
