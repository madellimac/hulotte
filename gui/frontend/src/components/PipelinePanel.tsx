import React from 'react';
import { ProjectData } from '../services/api';

interface PipelinePanelProps {
  project: ProjectData | null;
}

export const PipelinePanel: React.FC<PipelinePanelProps> = ({ project }) => {
  const nodes = project?.pipeline_nodes || [];

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>🔄 Pipeline du Projet</h2>

      {!project ? (
        <p style={styles.empty}>Veuillez sélectionner un projet pour voir son pipeline.</p>
      ) : (
        <div style={styles.pipelineContainer}>
          {nodes.map((node, index) => (
            <React.Fragment key={index}>
              <div style={styles.nodeBox}>
                <span style={styles.nodeText}>{node}</span>
              </div>
              {index < nodes.length - 1 && (
                <div style={styles.arrow}>↓</div>
              )}
            </React.Fragment>
          ))}
        </div>
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
};
