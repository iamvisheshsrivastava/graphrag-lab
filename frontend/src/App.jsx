import { useState } from 'react'
import Sidebar from './components/Sidebar'
import RequirementsPanel from './components/RequirementsPanel'
import GraphViewer from './components/GraphViewer'
import QueryPanel from './components/QueryPanel'
import VerificationPanel from './components/VerificationPanel'
import TraceabilityPanel from './components/TraceabilityPanel'
import CypherConsole from './components/CypherConsole'

const PAGE_TITLES = {
  requirements: 'Requirements Manager',
  graph:        'Knowledge Graph Viewer',
  query:        'GraphRAG Query Interface',
  verify:       'Requirements Verification',
  traceability: 'Traceability Matrix',
  cypher:       'Cypher Console',
}

const PAGE_SUBTITLES = {
  requirements: 'Load, inspect, and manage structured parking system requirements',
  graph:        'Interactive knowledge graph — nodes are requirements & ontology concepts',
  query:        'Natural language queries answered by graph-guided retrieval + LLM generation',
  verify:       'Deterministic rule-based verification against ISO 26262 and SAE J3016',
  traceability: 'Upstream/downstream dependency tracing for certification evidence',
  cypher:       'Direct Cypher queries against the Neo4j AuraDB knowledge graph',
}

export default function App() {
  const [page, setPage] = useState('requirements')
  const [graph, setGraph] = useState(null)
  const [requirements, setRequirements] = useState([])
  const [highlightNodes, setHighlightNodes] = useState([])

  function handleGraphBuilt(g, reqs) {
    setGraph(g)
    setRequirements(reqs)
    setPage('graph')
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar active={page} onNav={setPage} />

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="shrink-0 px-6 py-4 border-b border-slate-700/50 bg-surface-900/50 backdrop-blur">
          <h1 className="text-base font-semibold text-slate-100">{PAGE_TITLES[page]}</h1>
          <p className="text-xs text-slate-500 mt-0.5">{PAGE_SUBTITLES[page]}</p>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-hidden p-5">
          {page === 'requirements' && (
            <RequirementsPanel onGraphBuilt={handleGraphBuilt} />
          )}
          {page === 'graph' && (
            <GraphViewer graph={graph} highlightNodes={highlightNodes} />
          )}
          {page === 'query' && (
            <QueryPanel graph={graph} onHighlight={nodes => {
              setHighlightNodes(nodes)
            }} />
          )}
          {page === 'verify' && (
            <VerificationPanel requirements={requirements} />
          )}
          {page === 'traceability' && (
            <TraceabilityPanel graph={graph} requirements={requirements} />
          )}
          {page === 'cypher' && (
            <CypherConsole />
          )}
        </div>
      </main>
    </div>
  )
}
