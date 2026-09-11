import React from 'react';
import { ProjectData } from '../services/api';

interface ActionsPanelProps {
  project: ProjectData | null;
  onGenerate: () => void;
  onBuild: () => void;
  onRun: () => void;
  onStop: () => void;
  status: string;
}

export const ActionsPanel: React.FC<ActionsPanelProps> = ({
  project,
  onGenerate,
  onBuild,
  onRun,
  onStop,
  status,
}) => {
  const isDisabled = !project;
  const isBuilding = status === 'building';
  const isRunning = status === 'running';

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>⚙️ Actions</h2>

      <div style={styles.buttonGroup}>
        <button
          style={{ ...styles.btn, ...styles.generateBtn }}
          disabled={isDisabled || isBuilding || isRunning}
          onClick={onGenerate}
        >
          Generate
        </button>

        <button
          style={{ ...styles.btn, ...styles.buildBtn }}
          disabled={isDisabled || isBuilding || isRunning}
          onClick={onBuild}
        >
          {isBuilding ? 'Building...' : 'Build'}
        </button>

        <button
          style={{ ...styles.btn, ...styles.runBtn }}
          disabled={isDisabled || isBuilding || isRunning}
          onClick={onRun}
        >
          {isRunning ? 'Running...' : 'Run'}
        </button>

        <button
          style={{ ...styles.btn, ...styles.stopBtn }}
          disabled={isDisabled || (!isBuilding && !isRunning)}
          onClick={onStop}
        >
          Stop
        </button>
      </div>

      {project && (
        <div style={styles.statusIndicator}>
          <span>Statut actuel : </span>
          <strong style={getStatusStyle(status)}>{status.toUpperCase()}</strong>
        </div>
      )}
    </div>
  );
};

const getStatusStyle = (status: string): React.CSSProperties => {
  switch (status) {
    case 'building':
      return { color: '#f59e0b' };
    case 'running':
      return { color: '#10b981' };
    case 'error':
      return { color: '#ef4444' };
    default:
      return { color: '#94a3b8' };
  }
};

const styles: { [key: string]: React.CSSProperties } = {
  card: {
    backgroundColor: '#1e293b',
    borderRadius: '8px',
    padding: '16px',
    border: '1px solid #334155',
  },
  title: {
    margin: '0 0 16px 0',
    fontSize: '1.2rem',
    color: '#38bdf8',
  },
  buttonGroup: {
    display: 'flex',
    gap: '12px',
    flexWrap: 'wrap',
  },
  btn: {
    flex: 1,
    minWidth: '100px',
    padding: '10px 16px',
    borderRadius: '6px',
    border: 'none',
    color: '#ffffff',
    fontWeight: 'bold',
    cursor: 'pointer',
    fontSize: '0.9rem',
    transition: 'opacity 0.2s',
  },
  generateBtn: {
    backgroundColor: '#6366f1',
  },
  buildBtn: {
    backgroundColor: '#d97706',
  },
  runBtn: {
    backgroundColor: '#059669',
  },
  stopBtn: {
    backgroundColor: '#dc2626',
  },
  statusIndicator: {
    marginTop: '16px',
    fontSize: '0.85rem',
    color: '#cbd5e1',
  },
};
