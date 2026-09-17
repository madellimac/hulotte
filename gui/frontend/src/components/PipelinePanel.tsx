import React, { useEffect, useState } from 'react';
import { openProjectFile, ProjectData, PipelineNode } from '../services/api';

interface PipelinePanelProps {
  project: ProjectData | null;
}

// Human-readable labels for manifest fields shown in the detail panel.
const FIELD_LABELS: Record<string, string> = {
  type: 'Type',
  id: 'ID',
  enabled: 'Activé',
  module_name: 'Nom du module',
  class_name: 'Classe C++',
  kind: 'Variante',
  source: 'Fichier source',
  header: 'Fichier header',
  wrapper_source: 'Wrapper (simulation)',
  core_source: 'Core (synthèse FPGA)',
};

// Fields already shown as the node title or handled separately.
const HIDDEN_FIELDS = new Set(['name', 'generic']);

const NODE_COLORS: Record<string, { backgroundColor: string; borderColor: string }> = {
  streampu: { backgroundColor: '#082f49', borderColor: '#0284c7' },
  aff3ct: { backgroundColor: '#042f2e', borderColor: '#0f766e' },
  custom: { backgroundColor: '#052e16', borderColor: '#16a34a' },
  hardware: { backgroundColor: '#431407', borderColor: '#d97706' },
  uart: { backgroundColor: '#450a0a', borderColor: '#dc2626' },
  unknown: { backgroundColor: '#1e293b', borderColor: '#64748b' },
};

const getNodeCategory = (type: string): string => {
  switch (type) {
    case 'source':
      return 'streampu';
    case 'aff3ct':
      return 'aff3ct';
    case 'custom':
    case 'comparator':
      return 'custom';
    case 'hardware':
      return 'hardware';
    case 'uart':
      return 'uart';
    default:
      return 'unknown';
  }
};

const NODE_CATEGORY_LABELS: Record<string, string> = {
  streampu: 'StreamPU',
  aff3ct: 'AFF3CT',
  custom: 'Custom',
  hardware: 'Hardware Simulation',
  uart: 'UART / HIL',
  unknown: 'Unknown',
};

const getNodeCategoryLabel = (type: string): string =>
  NODE_CATEGORY_LABELS[getNodeCategory(type)];

const FILE_FIELD_LABELS: Record<string, string> = {
  source: 'Source',
  header: 'Header',
  wrapper_source: 'Wrapper',
  core_source: 'Core',
};

export const PipelinePanel: React.FC<PipelinePanelProps> = ({ project }) => {
  const nodes = project?.pipeline_nodes || [];
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [openFileMessage, setOpenFileMessage] = useState<string | null>(null);

  // Reset the selection whenever the selected project changes.
  useEffect(() => {
    setSelectedIndex(null);
    setOpenFileMessage(null);
  }, [project?.name]);

  const selectedNode: PipelineNode | null =
    selectedIndex !== null && selectedIndex < nodes.length ? nodes[selectedIndex] : null;

  const availableFiles = selectedNode && !selectedNode.generic
    ? Object.entries(FILE_FIELD_LABELS)
      .map(([field, label]) => ({ field, label, path: selectedNode[field as keyof PipelineNode] }))
      .filter((file): file is { field: string; label: string; path: string } => typeof file.path === 'string' && file.path.length > 0)
    : [];

  const handleOpenFile = async (path: string) => {
    if (!project || !selectedNode) return;
    setOpenFileMessage(null);
    try {
      const result = await openProjectFile(project.name, path);
      setOpenFileMessage(`Fichier ouvert : ${result.path}`);
    } catch (error) {
      setOpenFileMessage(error instanceof Error ? error.message : 'Impossible d\'ouvrir le fichier');
    }
  };

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>🔄 Pipeline du Projet</h2>

      {!project ? (
        <p style={styles.empty}>Veuillez sélectionner un projet pour voir son pipeline.</p>
      ) : (
        <>
          <div style={styles.pipelineContainer}>
            {nodes.map((node, index) => (
              <React.Fragment key={index}>
                <button
                  type="button"
                  style={{
                    ...styles.nodeBox,
                    ...NODE_COLORS[getNodeCategory(node.type)],
                    ...(index === selectedIndex ? styles.nodeBoxSelected : {}),
                  }}
                  onClick={() => setSelectedIndex(index === selectedIndex ? null : index)}
                >
                  <span style={styles.nodeText}>{node.name}</span>
                </button>
                {index < nodes.length - 1 && <div style={styles.arrow}>↓</div>}
              </React.Fragment>
            ))}
          </div>

          <div style={styles.detailsBox}>
            {!selectedNode ? (
              <span style={styles.empty}>Cliquez sur un module pour voir ses détails.</span>
            ) : (
              <div>
                <div style={styles.detailsHeader}>{selectedNode.name}</div>
                <div
                  style={{
                    ...styles.categoryBadge,
                    ...NODE_COLORS[getNodeCategory(selectedNode.type)],
                  }}
                >
                  {getNodeCategoryLabel(selectedNode.type)}
                </div>
                {selectedNode.generic && (
                  <div style={styles.genericNotice}>
                    Module générique par défaut (aucune entrée dédiée dans hulotte.project.json).
                  </div>
                )}
                <dl style={styles.detailsList}>
                  {Object.entries(selectedNode)
                    .filter(([key, value]) => !HIDDEN_FIELDS.has(key) && value !== undefined && value !== null)
                    .map(([key, value]) => (
                      <React.Fragment key={key}>
                        <dt style={styles.detailsTerm}>{FIELD_LABELS[key] || key}</dt>
                        <dd style={styles.detailsValue}>
                          {key === 'type'
                            ? getNodeCategoryLabel(selectedNode.type)
                            : String(value)}
                        </dd>
                      </React.Fragment>
                    ))}
                </dl>
                {availableFiles.length > 0 && (
                  <div style={styles.fileActions}>
                    <div style={styles.fileActionsTitle}>Ouvrir dans l’éditeur</div>
                    {availableFiles.map((file) => (
                      <button
                        key={file.field}
                        type="button"
                        style={styles.openFileButton}
                        onClick={() => handleOpenFile(file.path)}
                      >
                        {file.label}
                      </button>
                    ))}
                  </div>
                )}
                {availableFiles.length === 0 && (
                  <div style={styles.noFileNotice}>
                    Aucun fichier source associé à ce bloc.
                  </div>
                )}
                {openFileMessage && <div style={styles.openFileMessage}>{openFileMessage}</div>}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  card: {
    backgroundColor: '#1e293b',
    borderRadius: '8px',
    padding: '16px',
    border: '1px solid #334155',
    minHeight: '200px',
  },
  title: {
    margin: '0 0 16px 0',
    fontSize: '1.2rem',
    color: '#38bdf8',
  },
  empty: {
    color: '#94a3b8',
    fontSize: '0.9rem',
    fontStyle: 'italic',
  },
  pipelineContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '8px',
    padding: '16px 0',
  },
  nodeBox: {
    backgroundColor: '#0f172a',
    border: '1px solid #3b82f6',
    borderRadius: '6px',
    padding: '10px 20px',
    minWidth: '200px',
    textAlign: 'center',
    boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
    cursor: 'pointer',
    font: 'inherit',
  },
  nodeBoxSelected: {
    borderColor: '#f8fafc',
    boxShadow: '0 0 0 2px rgba(248, 250, 252, 0.75)',
  },
  nodeText: {
    color: '#f8fafc',
    fontSize: '0.9rem',
    fontWeight: '500',
  },
  arrow: {
    color: '#38bdf8',
    fontSize: '1.2rem',
    fontWeight: 'bold',
  },
  detailsBox: {
    marginTop: '12px',
    padding: '12px',
    backgroundColor: '#0f172a',
    borderRadius: '6px',
    border: '1px solid #334155',
    minHeight: '48px',
  },
  detailsHeader: {
    color: '#38bdf8',
    fontWeight: 'bold',
    marginBottom: '8px',
  },
  categoryBadge: {
    display: 'inline-block',
    color: '#f8fafc',
    borderRadius: '4px',
    border: '1px solid',
    padding: '4px 8px',
    fontSize: '0.8rem',
    fontWeight: 'bold',
    marginBottom: '10px',
  },
  genericNotice: {
    color: '#94a3b8',
    fontSize: '0.8rem',
    fontStyle: 'italic',
    marginBottom: '8px',
  },
  detailsList: {
    display: 'grid',
    gridTemplateColumns: 'auto 1fr',
    columnGap: '12px',
    rowGap: '4px',
    margin: 0,
  },
  detailsTerm: {
    color: '#94a3b8',
    fontSize: '0.8rem',
    margin: 0,
  },
  detailsValue: {
    color: '#f8fafc',
    fontSize: '0.85rem',
    margin: 0,
    wordBreak: 'break-all',
  },
  fileActions: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: '8px',
    marginTop: '12px',
  },
  fileActionsTitle: {
    width: '100%',
    color: '#cbd5e1',
    fontSize: '0.8rem',
    fontWeight: 'bold',
  },
  openFileButton: {
    backgroundColor: '#334155',
    color: '#f8fafc',
    border: '1px solid #64748b',
    borderRadius: '4px',
    padding: '6px 10px',
    cursor: 'pointer',
    font: 'inherit',
    fontSize: '0.8rem',
  },
  openFileMessage: {
    color: '#cbd5e1',
    fontSize: '0.8rem',
    marginTop: '8px',
    wordBreak: 'break-all',
  },
  noFileNotice: {
    color: '#94a3b8',
    fontSize: '0.8rem',
    fontStyle: 'italic',
    marginTop: '12px',
  },
};
