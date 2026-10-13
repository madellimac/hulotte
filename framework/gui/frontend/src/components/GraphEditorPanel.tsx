import React, { useEffect, useState } from 'react';
import {
  addGraphBlock,
  connectGraphBlocks,
  fetchGraphPalette,
  GraphPaletteEntry,
  GraphPayload,
  saveProjectGraph,
  validateGraph,
} from '../services/api';

type PortInfo = {
  name: string;
  task: string;
  direction: 'input' | 'output';
};

type SelectedPort = {
  blockId: string;
  task: string;
  port: string;
};

const emptyGraph: GraphPayload = { modules: {}, connections: [] };

function resolvePortTask(module: any, direction: 'input' | 'output', portName: string): string {
  const sockets = (module?.sockets ?? {}) as Record<string, any>;
  for (const [taskName, taskSpec] of Object.entries(sockets)) {
    if (!taskSpec || typeof taskSpec !== 'object') continue;
    const typedTaskSpec = taskSpec as Record<string, any>;
    const ports = typedTaskSpec[direction === 'input' ? 'inputs' : 'outputs'];
    if (!ports || typeof ports !== 'object') continue;
    if (Object.prototype.hasOwnProperty.call(ports, portName)) {
      return taskName;
    }
  }
  return 'main';
}

function collectPorts(module: any): { inputs: PortInfo[]; outputs: PortInfo[] } {
  const result = { inputs: [] as PortInfo[], outputs: [] as PortInfo[] };
  if (!module?.sockets || typeof module.sockets !== 'object') {
    return result;
  }

  for (const [taskName, taskSpec] of Object.entries(module.sockets as Record<string, any>)) {
    if (!taskSpec || typeof taskSpec !== 'object') continue;
    const typedTaskSpec = taskSpec as Record<string, any>;
    const inputs = typedTaskSpec.inputs ?? {};
    const outputs = typedTaskSpec.outputs ?? {};

    Object.keys(inputs).forEach((portName) => {
      result.inputs.push({ name: portName, task: taskName, direction: 'input' });
    });
    Object.keys(outputs).forEach((portName) => {
      result.outputs.push({ name: portName, task: taskName, direction: 'output' });
    });
  }

  return result;
}

function paletteCategory(block: GraphPaletteEntry): string {
  return block.family && block.family !== 'generic' ? block.family : block.kind;
}

function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    streampu: 'StreamPU',
    aff3ct: 'AFF3CT',
    hardware: 'Hardware',
    custom: 'Custom',
    source: 'Sources',
    utility: 'Utilities',
  };
  return labels[category] ?? category;
}

interface GraphEditorPanelProps {
  projectName?: string;
}

export const GraphEditorPanel: React.FC<GraphEditorPanelProps> = ({ projectName }) => {
  const [palette, setPalette] = useState<GraphPaletteEntry[]>([]);
  const [graph, setGraph] = useState<GraphPayload>(emptyGraph);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [selectedPort, setSelectedPort] = useState<SelectedPort | null>(null);
  const [status, setStatus] = useState<string>('Palette ready');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const loadPalette = async () => {
      try {
        const data = await fetchGraphPalette();
        setPalette(data);
      } catch (error) {
        setStatus(error instanceof Error ? error.message : 'Unable to load palette');
      }
    };
    loadPalette();
  }, []);

  const addBlock = async (catalogId: string) => {
    setIsLoading(true);
    try {
      const index = Object.keys(graph.modules).length;
      const blockId = `${catalogId}_${index + 1}`;
      const x = 40 + (index % 3) * 260;
      const y = 40 + Math.floor(index / 3) * 220;

      const response = await addGraphBlock({
        catalog_id: catalogId,
        block_id: blockId,
        x,
        y,
        canvas: graph,
      });
      const nextGraph = response.canvas ?? graph;
      setGraph(nextGraph);
      setPositions((current) => ({ ...current, [blockId]: { x, y } }));
      setStatus(`Added ${blockId}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to add block');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePortClick = async (blockId: string, port: PortInfo) => {
    if (port.direction === 'output') {
      setSelectedPort({ blockId, task: port.task, port: port.name });
      setStatus(`Selected output ${blockId}.${port.task}.${port.name}`);
      return;
    }

    if (!selectedPort) {
      setStatus(`Select an output port first`);
      return;
    }

    try {
      const response = await connectGraphBlocks({
        source_block: selectedPort.blockId,
        source_task: selectedPort.task,
        source_port: selectedPort.port,
        target_block: blockId,
        target_task: port.task,
        target_port: port.name,
        canvas: graph,
      });
      setGraph(response.canvas ?? graph);
      setSelectedPort(null);
      setStatus(`Connected ${selectedPort.blockId}.${selectedPort.task}.${selectedPort.port} -> ${blockId}.${port.task}.${port.name}`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Connection failed');
    }
  };

  const handleValidate = async () => {
    try {
      const result = await validateGraph(graph);
      if (result.valid) {
        const validatedGraph = result.payload ?? graph;
        if (!projectName) {
          setStatus('Graph validé. Crée d\'abord un projet pour l\'enregistrer.');
          return;
        }
        await saveProjectGraph(projectName, validatedGraph);
        setGraph(validatedGraph);
        setStatus('Graph validé et enregistré dans le projet');
      } else {
        setStatus(result.error ?? 'Invalid graph');
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Validation failed');
    }
  };

  const clearGraph = () => {
    setGraph(emptyGraph);
    setPositions({});
    setSelectedPort(null);
    setStatus('Canvas cleared');
  };

  const paletteGroups = palette.reduce<Record<string, GraphPaletteEntry[]>>((groups, block) => {
    const category = paletteCategory(block);
    groups[category] = groups[category] ?? [];
    groups[category].push(block);
    return groups;
  }, {});

  const connectionLine = (connection: { from: string; to: string }, index: number) => {
    const sourceBlockId = connection.from.split('.')[0];
    const targetBlockId = connection.to.split('.')[0];
    const source = positions[sourceBlockId];
    const target = positions[targetBlockId];
    if (!source || !target) return null;

    return (
      <line
        key={`${connection.from}-${connection.to}-${index}`}
        x1={source.x + 208}
        y1={source.y + 65}
        x2={target.x}
        y2={target.y + 65}
        stroke="#fbbf24"
        strokeWidth="3"
        markerEnd="url(#connection-arrow)"
      />
    );
  };

  return (
    <div style={styles.card}>
      <div style={styles.headerRow}>
        <h2 style={styles.title}>🧩 Graph editor</h2>
        <div style={styles.actions}>
          <button style={styles.secondaryBtn} onClick={clearGraph}>Clear</button>
          <button style={styles.primaryBtn} onClick={handleValidate} disabled={isLoading}>Validate</button>
        </div>
      </div>

      <div style={styles.workspace}>
        <div style={styles.palettePanel}>
          <h3 style={styles.subtitle}>Palette</h3>
          {palette.length === 0 ? (
            <div style={styles.empty}>Loading palette…</div>
          ) : (
            Object.entries(paletteGroups).map(([category, blocks]) => (
              <section key={category} style={styles.paletteGroup}>
                <h4 style={styles.categoryTitle}>{categoryLabel(category)}</h4>
                {blocks.map((block) => (
                  <button
                    key={block.catalog_id}
                    style={styles.paletteItem}
                    onClick={() => addBlock(block.catalog_id)}
                    disabled={isLoading}
                  >
                    <span style={styles.paletteLabel}>{block.label}</span>
                    <span style={styles.paletteMeta}>{block.kind}</span>
                  </button>
                ))}
              </section>
            ))
          )}
        </div>

        <div style={styles.canvasPanel}>
          <div style={styles.canvasHeader}>Canvas</div>
          <svg style={styles.connectionLayer} aria-label="Graph connections">
            <defs>
              <marker id="connection-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                <path d="M0,0 L8,4 L0,8 z" fill="#fbbf24" />
              </marker>
            </defs>
            {graph.connections.map(connectionLine)}
          </svg>
          {Object.entries(graph.modules).length === 0 ? (
            <div style={styles.canvasEmpty}>Add a block from the palette to begin.</div>
          ) : (
            Object.entries(graph.modules).map(([blockId, module]) => {
              const portInfo = collectPorts(module);
              const position = positions[blockId] ?? { x: 80, y: 80 };

              return (
                <div
                  key={blockId}
                  style={{
                    ...styles.block,
                    left: position.x,
                    top: position.y,
                  }}
                >
                  <div style={styles.blockTitle}>{blockId}</div>

                  <div style={styles.portList}>
                    {portInfo.inputs.map((port) => (
                      <button
                        key={`${blockId}-in-${port.name}`}
                        style={styles.portButtonInput}
                        onClick={() => handlePortClick(blockId, port)}
                      >
                        {port.name}
                      </button>
                    ))}
                  </div>

                  <div style={styles.portList}>
                    {portInfo.outputs.map((port) => (
                      <button
                        key={`${blockId}-out-${port.name}`}
                        style={styles.portButtonOutput}
                        onClick={() => handlePortClick(blockId, port)}
                      >
                        {port.name}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div style={styles.footer}>
        <div style={styles.status}>{status}</div>
        <pre style={styles.jsonBox}>{JSON.stringify(graph, null, 2)}</pre>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  card: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '16px',
    color: '#e2e8f0',
  },
  headerRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '12px',
  },
  title: {
    margin: 0,
    fontSize: '1.1rem',
    color: '#7dd3fc',
  },
  actions: {
    display: 'flex',
    gap: '8px',
  },
  primaryBtn: {
    backgroundColor: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 12px',
    cursor: 'pointer',
  },
  secondaryBtn: {
    backgroundColor: '#334155',
    color: '#e2e8f0',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 12px',
    cursor: 'pointer',
  },
  workspace: {
    display: 'grid',
    gridTemplateColumns: '260px minmax(0, 1fr)',
    gap: '12px',
    alignItems: 'start',
  },
  palettePanel: {
    backgroundColor: '#111827',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '12px',
    minHeight: '200px',
  },
  subtitle: {
    margin: '0 0 12px',
    color: '#a5f3fc',
    fontSize: '0.95rem',
  },
  paletteGroup: {
    marginBottom: '14px',
  },
  categoryTitle: {
    margin: '0 0 6px',
    color: '#fbbf24',
    fontSize: '0.75rem',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
  },
  empty: {
    color: '#94a3b8',
    fontSize: '0.85rem',
  },
  paletteItem: {
    width: '100%',
    backgroundColor: '#1e293b',
    border: '1px solid #475569',
    borderRadius: '8px',
    color: '#e2e8f0',
    marginBottom: '8px',
    padding: '8px 10px',
    textAlign: 'left',
    cursor: 'pointer',
  },
  paletteLabel: {
    display: 'block',
    fontWeight: 600,
    marginBottom: '4px',
  },
  paletteMeta: {
    display: 'block',
    color: '#93c5fd',
    fontSize: '0.75rem',
  },
  canvasPanel: {
    position: 'relative',
    backgroundColor: '#0b1220',
    border: '1px solid #334155',
    borderRadius: '8px',
    minHeight: '520px',
    height: '520px',
    overflow: 'auto',
  },
  canvasHeader: {
    backgroundColor: '#111827',
    borderBottom: '1px solid #334155',
    padding: '8px 12px',
    color: '#bfdbfe',
    fontSize: '0.85rem',
  },
  connectionLayer: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    pointerEvents: 'none',
    zIndex: 1,
    overflow: 'visible',
  },
  canvasEmpty: {
    padding: '20px',
    color: '#94a3b8',
    textAlign: 'center',
  },
  block: {
    position: 'absolute',
    width: '200px',
    backgroundColor: '#1f2937',
    border: '1px solid #60a5fa',
    borderRadius: '8px',
    padding: '8px',
    boxShadow: '0 0 0 1px rgba(96,165,250,0.2)',
    minHeight: '110px',
    zIndex: 2,
  },
  blockTitle: {
    color: '#dbeafe',
    fontSize: '0.8rem',
    fontWeight: 700,
    marginBottom: '8px',
    wordBreak: 'break-word',
  },
  portList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    marginTop: '6px',
  },
  portButtonInput: {
    border: '1px solid #22c55e',
    backgroundColor: '#052e16',
    color: '#dcfce7',
    borderRadius: '4px',
    padding: '4px 6px',
    textAlign: 'left',
    cursor: 'pointer',
    fontSize: '0.75rem',
  },
  portButtonOutput: {
    border: '1px solid #f59e0b',
    backgroundColor: '#451a03',
    color: '#fef3c7',
    borderRadius: '4px',
    padding: '4px 6px',
    textAlign: 'left',
    cursor: 'pointer',
    fontSize: '0.75rem',
  },
  footer: {
    marginTop: '12px',
  },
  status: {
    marginBottom: '8px',
    color: '#bfdbfe',
    fontSize: '0.8rem',
  },
  jsonBox: {
    backgroundColor: '#020817',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '10px',
    color: '#cbd5e1',
    fontSize: '0.72rem',
    overflow: 'auto',
    maxHeight: '220px',
    margin: 0,
  },
};
