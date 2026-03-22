import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import ReactFlow, {
  Node,
  Edge,
  Connection,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { useAuth } from '../lib/auth'
import { apiGet } from '../lib/apiClient'

const ADMIN_USER_ID = '441f9c1f-9428-477e-a04f-fb8d5e654ec2'

// ─── Types ───────────────────────────────────────────────────────────────

interface ArchNode {
  id: string
  label: string
  layer: string
  status: string
  description: string
  code_path?: string
  git_sha?: string
  prompt_version?: string
  prompt_file?: string
  pseudologic?: string
  broader_context?: string
  wos?: string[]
  open_questions?: string[]
}

interface ArchEdge {
  id: string
  source: string
  target: string
  label?: string
}

interface ArchData {
  nodes: ArchNode[]
  edges: ArchEdge[]
}

interface AuditRow {
  detection_audit_id: string
  content: string
  sender_name: string | null
  parsed_result: Record<string, unknown> | null
  model: string | null
  created_at: string | null
}

// ─── Constants ───────────────────────────────────────────────────────────

type Layer = 'user_flow' | 'signal_pipeline' | 'commitment_lifecycle' | 'evaluation' | 'integrations'

const LAYERS: { id: Layer; label: string; color: string }[] = [
  { id: 'user_flow', label: 'User Flow', color: '#6366f1' },
  { id: 'signal_pipeline', label: 'Signal Pipeline', color: '#0ea5e9' },
  { id: 'commitment_lifecycle', label: 'Commitment Lifecycle', color: '#8b5cf6' },
  { id: 'evaluation', label: 'Evaluation', color: '#f59e0b' },
  { id: 'integrations', label: 'Integrations', color: '#10b981' },
]

const STATUS_STYLES: Record<string, { bg: string; border: string; text: string; borderStyle?: string }> = {
  stable: { bg: '#f0fdf4', border: '#22c55e', text: '#15803d' },
  in_progress: { bg: '#eff6ff', border: '#3b82f6', text: '#1d4ed8' },
  planned: { bg: '#f9fafb', border: '#9ca3af', text: '#6b7280', borderStyle: 'dashed' },
  broken: { bg: '#fef2f2', border: '#ef4444', text: '#dc2626' },
  decision_needed: { bg: '#fffbeb', border: '#f59e0b', text: '#d97706' },
}

const STATUS_BADGE: Record<string, { bg: string; text: string }> = {
  stable: { bg: '#dcfce7', text: '#15803d' },
  in_progress: { bg: '#dbeafe', text: '#1d4ed8' },
  planned: { bg: '#f3f4f6', text: '#6b7280' },
  broken: { bg: '#fee2e2', text: '#dc2626' },
  decision_needed: { bg: '#fef3c7', text: '#d97706' },
}

const LAYOUT_STORAGE_KEY = 'rippled-arch-layout'

// ─── Layout helpers ──────────────────────────────────────────────────────

const LAYER_Y: Record<string, number> = {
  user_flow: 0,
  signal_pipeline: 280,
  commitment_lifecycle: 560,
  evaluation: 280,
  integrations: 560,
}

const LAYER_X_OFFSET: Record<string, number> = {
  user_flow: 0,
  signal_pipeline: 0,
  commitment_lifecycle: 0,
  evaluation: 900,
  integrations: 900,
}

function getSavedPositions(): Record<string, { x: number; y: number }> {
  try {
    const raw = localStorage.getItem(LAYOUT_STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore corrupt data */ }
  return {}
}

function layoutNodes(archNodes: ArchNode[], applySaved = true): Node[] {
  const layerCounters: Record<string, number> = {}
  const saved = applySaved ? getSavedPositions() : {}

  return archNodes.map((n) => {
    const layerIdx = layerCounters[n.layer] ?? 0
    layerCounters[n.layer] = layerIdx + 1

    const cols = n.layer === 'commitment_lifecycle' ? 4 : n.layer === 'user_flow' ? 5 : 4
    const row = Math.floor(layerIdx / cols)
    const col = layerIdx % cols

    const x = (LAYER_X_OFFSET[n.layer] ?? 0) + col * 210
    const y = (LAYER_Y[n.layer] ?? 0) + row * 100

    const position = saved[n.id] ?? { x, y }
    const statusStyle = STATUS_STYLES[n.status] ?? STATUS_STYLES.stable

    return {
      id: n.id,
      position,
      data: { label: n.label, archNode: n },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      style: {
        background: statusStyle.bg,
        border: `2px ${statusStyle.borderStyle ?? 'solid'} ${statusStyle.border}`,
        borderRadius: '8px',
        padding: '8px 12px',
        fontSize: '12px',
        fontWeight: 600,
        color: statusStyle.text,
        minWidth: '160px',
        textAlign: 'center' as const,
      },
    }
  })
}

function layoutEdges(archEdges: ArchEdge[]): Edge[] {
  return archEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#d1d5db', strokeWidth: 1.5 },
    labelStyle: { fontSize: '10px', fill: '#9ca3af' },
    markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#d1d5db' },
  }))
}

// ─── Detail Panel ────────────────────────────────────────────────────────

function DetailPanel({
  node,
  onClose,
}: {
  node: ArchNode
  onClose: () => void
}) {
  const [promptExpanded, setPromptExpanded] = useState(!!node.prompt_file)
  const [promptText, setPromptText] = useState<string | null>(null)
  const [promptLoading, setPromptLoading] = useState(false)

  // Auto-load prompt when panel opens if node has a prompt_file
  useEffect(() => {
    if (!node.prompt_file) return
    setPromptLoading(true)
    fetch(`/${node.prompt_file}`)
      .then((resp) => {
        if (resp.ok) return resp.text()
        return '(Could not load prompt file)'
      })
      .then((text) => {
        setPromptText(text)
        setPromptExpanded(true)
      })
      .catch(() => {
        setPromptText('(Could not load prompt file)')
      })
      .finally(() => setPromptLoading(false))
  }, [node.prompt_file])

  const { data: auditRows } = useQuery({
    queryKey: ['admin', 'audit-sample', node.prompt_version],
    queryFn: () =>
      apiGet<AuditRow[]>(
        `/api/v1/admin/review/audit-sample?prompt_version=${encodeURIComponent(node.prompt_version!)}`
      ),
    enabled: !!node.prompt_version,
    staleTime: 60_000,
  })

  function togglePrompt() {
    setPromptExpanded(!promptExpanded)
  }

  const statusBadge = STATUS_BADGE[node.status] ?? STATUS_BADGE.stable
  const layerInfo = LAYERS.find((l) => l.id === node.layer)

  return (
    <div className="fixed right-0 top-0 h-full w-[400px] bg-white border-l border-[#e8e8e6] shadow-lg z-50 overflow-y-auto">
      <div className="sticky top-0 bg-white border-b border-[#e8e8e6] px-5 py-3 flex items-center justify-between">
        <h2 className="text-[15px] font-semibold text-[#191919] truncate">{node.label}</h2>
        <button
          onClick={onClose}
          className="text-[#9ca3af] hover:text-[#191919] transition-colors p-1"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* Status + Layer */}
        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium"
            style={{ backgroundColor: statusBadge.bg, color: statusBadge.text }}
          >
            {node.status.replace('_', ' ')}
          </span>
          {layerInfo && (
            <span
              className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium"
              style={{ backgroundColor: layerInfo.color + '20', color: layerInfo.color }}
            >
              {layerInfo.label}
            </span>
          )}
        </div>

        {/* Description */}
        <div>
          <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-1">Description</div>
          <p className="text-[13px] text-[#4b5563] leading-relaxed">{node.description}</p>
        </div>

        {/* Why it matters */}
        {node.broader_context && (
          <div>
            <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-1">Why it matters</div>
            <p className="text-[13px] text-[#4b5563] leading-relaxed">{node.broader_context}</p>
          </div>
        )}

        {/* Code path */}
        {node.code_path && (
          <div>
            <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-1">Code Path</div>
            <code className="text-[12px] text-[#2563eb] bg-[#f0f4ff] px-2 py-1 rounded font-mono">
              {node.code_path}
            </code>
            {node.git_sha && (
              <span className="ml-2 text-[11px] text-[#9ca3af]">@ {node.git_sha}</span>
            )}
          </div>
        )}

        {/* How it works (pseudologic) */}
        {node.pseudologic && (
          <div>
            <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-1">How it works</div>
            <div className="space-y-0.5">
              {node.pseudologic.split('\n').map((line, i) => (
                <p
                  key={i}
                  className="text-[12px] text-[#4b5563] leading-relaxed"
                  style={{ paddingLeft: line.startsWith('•') ? '8px' : '0' }}
                >
                  {line}
                </p>
              ))}
            </div>
          </div>
        )}

        {/* Open questions */}
        {node.open_questions && node.open_questions.length > 0 && (
          <div>
            <div className="text-[11px] font-semibold text-[#d97706] uppercase tracking-wide mb-1">Open Questions</div>
            <ul className="space-y-1">
              {node.open_questions.map((q, i) => (
                <li key={i} className="flex items-start gap-2 text-[13px] text-[#92400e]">
                  <span className="text-[#f59e0b] mt-0.5">?</span>
                  <span>{q}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Work orders */}
        {node.wos && node.wos.length > 0 && (
          <div>
            <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-1">Work Orders</div>
            <ul className="space-y-1">
              {node.wos.map((wo) => (
                <li key={wo} className="text-[12px] text-[#4b5563] font-mono bg-[#f9fafb] px-2 py-1 rounded">
                  {wo}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Prompt section */}
        {node.prompt_version && (
          <div className="border-t border-[#e8e8e6] pt-4">
            <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-2">Prompt</div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[12px] text-[#191919] font-medium">{node.prompt_version}</span>
              {node.prompt_file && (
                <button
                  onClick={togglePrompt}
                  className="text-[11px] text-[#2563eb] hover:text-[#1d4ed8] font-medium"
                >
                  {promptLoading ? 'Loading…' : promptExpanded ? 'Hide prompt' : 'View prompt'}
                </button>
              )}
            </div>

            {promptExpanded && promptText && (
              <pre className="text-[11px] text-[#4b5563] bg-[#f9fafb] border border-[#e8e8e6] rounded-md p-3 overflow-x-auto max-h-[300px] overflow-y-auto whitespace-pre-wrap font-mono leading-relaxed">
                {promptText}
              </pre>
            )}

            {/* Audit sample */}
            {auditRows && auditRows.length > 0 && (
              <div className="mt-3">
                <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-2">
                  Recent Audit ({auditRows.length})
                </div>
                <div className="space-y-2">
                  {auditRows.map((row) => (
                    <div
                      key={row.detection_audit_id}
                      className="bg-[#f9fafb] border border-[#e8e8e6] rounded-md p-3"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] text-[#6b7280]">
                          {row.sender_name || 'Unknown'}
                        </span>
                        <span className="text-[10px] text-[#9ca3af]">
                          {row.created_at
                            ? new Date(row.created_at).toLocaleDateString('en-US', {
                                month: 'short',
                                day: 'numeric',
                              })
                            : ''}
                        </span>
                      </div>
                      <p className="text-[12px] text-[#4b5563] leading-relaxed line-clamp-3">
                        {row.content}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Architecture Screen ─────────────────────────────────────────────────

export default function ArchitectureScreen() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const [selectedLayer, setSelectedLayer] = useState<Layer | null>(null)
  const [selectedNode, setSelectedNode] = useState<ArchNode | null>(null)
  const [archData, setArchData] = useState<ArchData | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  // Load architecture data from static JSON
  useEffect(() => {
    setArchData(null)
    setLoadError(null)
    fetch('/ops/architecture/rippled-arch.json')
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load: ${r.status}`)
        return r.json()
      })
      .then((data: ArchData) => setArchData(data))
      .catch((e) => setLoadError(e.message))
  }, [refreshKey])

  // Compute React Flow nodes/edges from data
  const rfNodes = useMemo(() => {
    if (!archData) return []
    return layoutNodes(archData.nodes)
  }, [archData])

  const rfEdges = useMemo(() => {
    if (!archData) return []
    return layoutEdges(archData.edges)
  }, [archData])

  // Apply layer filter — dim non-selected nodes
  const filteredNodes = useMemo(() => {
    if (!selectedLayer) return rfNodes
    return rfNodes.map((n) => {
      const archNode = n.data.archNode as ArchNode
      const isMatch = archNode.layer === selectedLayer
      return {
        ...n,
        style: {
          ...n.style,
          opacity: isMatch ? 1 : 0.15,
        },
      }
    })
  }, [rfNodes, selectedLayer])

  const filteredEdges = useMemo(() => {
    if (!selectedLayer) return rfEdges
    const visibleNodeIds = new Set(
      archData?.nodes.filter((n) => n.layer === selectedLayer).map((n) => n.id) ?? []
    )
    return rfEdges.map((e) => ({
      ...e,
      style: {
        ...e.style,
        opacity: visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target) ? 1 : 0.08,
      },
    }))
  }, [rfEdges, selectedLayer, archData])

  const [nodes, setNodes, onNodesChange] = useNodesState(filteredNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(filteredEdges)

  // Debounced save of node positions to localStorage
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const savePositions = useCallback((currentNodes: Node[]) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      const positions: Record<string, { x: number; y: number }> = {}
      currentNodes.forEach((n) => {
        positions[n.id] = { x: n.position.x, y: n.position.y }
      })
      localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(positions))
    }, 500)
  }, [])

  const handleNodesChange = useCallback(
    (changes: Parameters<typeof onNodesChange>[0]) => {
      onNodesChange(changes)
      // Save when a drag ends (position change with dragging=false)
      const hasDragEnd = changes.some(
        (c) => c.type === 'position' && 'dragging' in c && c.dragging === false
      )
      if (hasDragEnd) {
        // We need the updated nodes — use functional update to read latest
        setNodes((prev) => {
          savePositions(prev)
          return prev
        })
      }
    },
    [onNodesChange, savePositions, setNodes]
  )

  // Sync filtered nodes/edges when they change
  useEffect(() => {
    setNodes(filteredNodes)
  }, [filteredNodes, setNodes])

  useEffect(() => {
    setEdges(filteredEdges)
  }, [filteredEdges, setEdges])

  // Edge reconnection — same-node only
  const onEdgeUpdate = useCallback(
    (oldEdge: Edge, newConnection: Connection) => {
      if (
        newConnection.source === oldEdge.source &&
        newConnection.target === oldEdge.target
      ) {
        setEdges((eds) =>
          eds.map((e) =>
            e.id === oldEdge.id
              ? {
                  ...e,
                  sourceHandle: newConnection.sourceHandle ?? e.sourceHandle,
                  targetHandle: newConnection.targetHandle ?? e.targetHandle,
                }
              : e
          )
        )
      }
      // If source or target changed, reject (do nothing)
    },
    [setEdges]
  )

  // Reset layout to computed defaults
  const resetLayout = useCallback(() => {
    if (!archData) return
    localStorage.removeItem(LAYOUT_STORAGE_KEY)
    const freshNodes = layoutNodes(archData.nodes, false)
    // Re-apply layer filter if active
    if (selectedLayer) {
      setNodes(
        freshNodes.map((n) => ({
          ...n,
          style: {
            ...n.style,
            opacity: (n.data.archNode as ArchNode).layer === selectedLayer ? 1 : 0.15,
          },
        }))
      )
    } else {
      setNodes(freshNodes)
    }
  }, [archData, selectedLayer, setNodes])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const archNode = node.data.archNode as ArchNode
      setSelectedNode(archNode)
    },
    []
  )

  // Auth guard
  useEffect(() => {
    if (!loading && user?.id !== ADMIN_USER_ID) {
      navigate('/', { replace: true })
    }
  }, [loading, user, navigate])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#191919] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (user?.id !== ADMIN_USER_ID) return null

  if (loadError) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-[14px] text-[#991b1b]">Failed to load architecture data: {loadError}</div>
      </div>
    )
  }

  if (!archData) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#191919] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col bg-[#f9f9f8]">
      {/* Header */}
      <div className="bg-white border-b border-[#e8e8e6] h-[52px] flex items-center px-4 md:px-6 flex-shrink-0">
        <div className="flex items-center flex-shrink-0">
          <button
            onClick={() => navigate('/')}
            className="font-semibold text-[16px] text-[#191919] tracking-tight hover:text-[#6b7280] transition-colors"
          >
            rippled
          </button>
          <span className="ml-2 text-[11px] text-[#9ca3af] bg-[#f0f0ef] rounded-full px-2 py-0.5 font-medium">
            Admin
          </span>
        </div>
        <div className="flex items-center gap-1 mx-3 md:mx-auto">
          <button
            onClick={() => navigate('/admin')}
            className="text-[#6b7280] hover:text-[#191919] px-3 md:px-4 py-1 text-[13px] transition-colors"
          >
            Signal Review
          </button>
          <button
            onClick={() => navigate('/admin')}
            className="text-[#6b7280] hover:text-[#191919] px-3 md:px-4 py-1 text-[13px] transition-colors"
          >
            Outcome Review
          </button>
          <button className="bg-[#191919] text-white rounded-full px-3 md:px-4 py-1 text-[13px] font-medium">
            Architecture
          </button>
        </div>
        <div className="ml-auto flex-shrink-0 flex items-center gap-2">
          <button
            onClick={resetLayout}
            className="text-[13px] text-[#6b7280] hover:text-[#191919] border border-[#e8e8e6] hover:border-[#d1d5db] px-3 py-1 rounded transition-colors"
          >
            Reset layout
          </button>
          <button
            onClick={() => setRefreshKey((k) => k + 1)}
            disabled={!archData && !loadError}
            className="text-[13px] text-[#6b7280] hover:text-[#191919] border border-[#e8e8e6] hover:border-[#d1d5db] px-3 py-1 rounded transition-colors disabled:opacity-50"
          >
            {!archData && !loadError ? (
              <span className="inline-flex items-center gap-1.5">
                <span className="w-3 h-3 border border-[#6b7280] border-t-transparent rounded-full animate-spin" />
                Loading
              </span>
            ) : (
              'Refresh'
            )}
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left panel: Layer filters */}
        <div className="w-[200px] bg-white border-r border-[#e8e8e6] flex-shrink-0 py-4 px-3">
          <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-3 px-1">
            Layers
          </div>
          <div className="space-y-1">
            <button
              onClick={() => setSelectedLayer(null)}
              className={`w-full text-left px-3 py-2 rounded-md text-[13px] transition-colors ${
                selectedLayer === null
                  ? 'bg-[#191919] text-white font-medium'
                  : 'text-[#4b5563] hover:bg-[#f0f0ef]'
              }`}
            >
              All Layers
            </button>
            {LAYERS.map((l) => (
              <button
                key={l.id}
                onClick={() => setSelectedLayer(selectedLayer === l.id ? null : l.id)}
                className={`w-full text-left px-3 py-2 rounded-md text-[13px] transition-colors flex items-center gap-2 ${
                  selectedLayer === l.id
                    ? 'bg-[#191919] text-white font-medium'
                    : 'text-[#4b5563] hover:bg-[#f0f0ef]'
                }`}
              >
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: l.color }}
                />
                {l.label}
              </button>
            ))}
          </div>

          {/* Legend */}
          <div className="mt-6 pt-4 border-t border-[#e8e8e6]">
            <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-3 px-1">
              Status
            </div>
            <div className="space-y-1.5 px-1">
              {Object.entries(STATUS_BADGE).map(([status, style]) => (
                <div key={status} className="flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-sm flex-shrink-0"
                    style={{
                      backgroundColor: style.bg,
                      border: `1.5px ${status === 'planned' ? 'dashed' : 'solid'} ${STATUS_STYLES[status]?.border}`,
                    }}
                  />
                  <span className="text-[11px] text-[#6b7280]">{status.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* React Flow canvas */}
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onEdgeUpdate={onEdgeUpdate}
            edgesUpdatable
            selectionOnDrag
            panOnDrag={[1, 2]}
            multiSelectionKeyCode={['Control', 'Meta']}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.3}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#e8e8e6" gap={20} />
            <Controls
              showInteractive={false}
              style={{ bottom: 16, left: 16 }}
            />
            <MiniMap
              nodeColor={(n) => {
                const archNode = n.data?.archNode as ArchNode | undefined
                if (!archNode) return '#e8e8e6'
                return STATUS_STYLES[archNode.status]?.border ?? '#e8e8e6'
              }}
              style={{ bottom: 16, right: selectedNode ? 416 : 16 }}
            />
          </ReactFlow>
        </div>

        {/* Detail panel */}
        {selectedNode && (
          <DetailPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
        )}
      </div>
    </div>
  )
}
