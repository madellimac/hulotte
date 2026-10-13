import React, { useState, useEffect } from 'react';
import {
  ProjectData,
  CreateProjectPayload,
  createProject,
  generateProject,
  buildProject,
  runProject,
  stopProject,
  fetchProjectStatus,
  fetchProjectLogs,
  refreshProject,
} from './services/api';
import { ProjectPanel } from './components/ProjectPanel';
import { ConsolePanel } from './components/ConsolePanel';
import { GraphEditorPanel } from './components/GraphEditorPanel';

export const App: React.FC = () => {
  const [selectedProject, setSelectedProject] = useState<ProjectData | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [status, setStatus] = useState<string>('idle');

  // Poll logs and status when a project is selected
  useEffect(() => {
    if (!selectedProject) return;

    const interval = setInterval(async () => {
      try {
        const s = await fetchProjectStatus(selectedProject.name);
        setStatus((prevStatus) => (prevStatus !== s.status ? s.status : prevStatus));

        const l = await fetchProjectLogs(selectedProject.name);
        setLogs((prevLogs) => {
          if (
            prevLogs.length === l.logs.length &&
            prevLogs.every((val, idx) => val === l.logs[idx])
          ) {
            return prevLogs;
          }
          return l.logs;
        });
      } catch (err) {
        console.error('Polling error', err);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [selectedProject]);

  const handleCreateProject = async (payload: CreateProjectPayload) => {
    const newProj = await createProject(payload);
    setSelectedProject(newProj);
  };

  const handleGenerate = async () => {
    if (!selectedProject) return;
    try {
      await generateProject(selectedProject.name);
      const refreshedProject = await refreshProject(selectedProject.name);
      setSelectedProject(refreshedProject);
      const l = await fetchProjectLogs(selectedProject.name);
      setLogs(l.logs);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleBuild = async () => {
    if (!selectedProject) return;
    try {
      await buildProject(selectedProject.name);
      setStatus('building');
      await refreshSelectedProject();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleRun = async () => {
    if (!selectedProject) return;
    try {
      await runProject(selectedProject.name);
      setStatus('running');
      await refreshSelectedProject();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleStop = async () => {
    if (!selectedProject) return;
    try {
      await stopProject(selectedProject.name);
      setStatus('idle');
      await refreshSelectedProject();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const refreshSelectedProject = async () => {
    if (!selectedProject) return;
    const refreshedProject = await refreshProject(selectedProject.name);
    setSelectedProject(refreshedProject);
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.appTitle}>🦉 Hulotte GUI</h1>

        <div style={styles.headerActions}>
          <button style={styles.headerBtn} onClick={handleGenerate} disabled={!selectedProject}>Generate</button>
          <button style={styles.headerBtnBuild} onClick={handleBuild} disabled={!selectedProject}>Build</button>
          <button style={styles.headerBtnRun} onClick={handleRun} disabled={!selectedProject}>Run</button>
          <button style={styles.headerBtnStop} onClick={handleStop} disabled={!selectedProject}>Stop</button>
          <span style={{ ...styles.statusBadge, ...getStatusColor(status) }}>{status.toUpperCase()}</span>
        </div>
      </header>

      <div style={styles.mainLayout}>
        <aside style={styles.leftPane}>
          <ProjectPanel
            selectedProject={selectedProject}
            onCreateProject={handleCreateProject}
          />
        </aside>

        <main style={styles.centerPane}>
          <GraphEditorPanel projectName={selectedProject?.name} />
        </main>
      </div>

      <div style={styles.bottomPane}>
        <ConsolePanel logs={logs} onClear={() => setLogs([])} />
      </div>
    </div>
  );
};

const getStatusColor = (status: string): React.CSSProperties => {
  switch (status) {
    case 'building':
      return { backgroundColor: '#78350f', color: '#fbbf24' };
    case 'running':
      return { backgroundColor: '#064e3b', color: '#6ee7b7' };
    case 'error':
      return { backgroundColor: '#7f1d1d', color: '#fca5a5' };
    default:
      return { backgroundColor: '#1e293b', color: '#cbd5e1' };
  }
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    maxWidth: '1600px',
    margin: '0 auto',
    padding: '20px',
    boxSizing: 'border-box',
    minHeight: '100vh',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
    paddingBottom: '16px',
    borderBottom: '1px solid #334155',
    gap: '16px',
  },
  appTitle: {
    margin: 0,
    fontSize: '1.5rem',
    color: '#f8fafc',
    fontWeight: 700,
  },
  headerActions: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexWrap: 'wrap',
  },
  headerBtn: {
    backgroundColor: '#3b82f6',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 12px',
    cursor: 'pointer',
    fontWeight: 600,
  },
  headerBtnBuild: {
    backgroundColor: '#d97706',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 12px',
    cursor: 'pointer',
    fontWeight: 600,
  },
  headerBtnRun: {
    backgroundColor: '#059669',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 12px',
    cursor: 'pointer',
    fontWeight: 600,
  },
  headerBtnStop: {
    backgroundColor: '#dc2626',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 12px',
    cursor: 'pointer',
    fontWeight: 600,
  },
  statusBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: '92px',
    padding: '8px 10px',
    borderRadius: '999px',
    fontSize: '0.75rem',
    fontWeight: 700,
    letterSpacing: '0.04em',
  },
  mainLayout: {
    display: 'grid',
    gridTemplateColumns: '320px minmax(0, 1fr)',
    gap: '20px',
    alignItems: 'start',
  },
  leftPane: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    minWidth: 0,
  },
  centerPane: {
    minWidth: 0,
  },
  bottomPane: {
    display: 'grid',
    gridTemplateColumns: '1fr 1.2fr',
    gap: '20px',
    marginTop: '20px',
  },
};
