import React, { useState, useEffect } from 'react';
import {
  ProjectData,
  CreateProjectPayload,
  fetchProjects,
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
import { PipelinePanel } from './components/PipelinePanel';
import { ActionsPanel } from './components/ActionsPanel';
import { ConsolePanel } from './components/ConsolePanel';

export const App: React.FC = () => {
  const [projects, setProjects] = useState<ProjectData[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectData | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [status, setStatus] = useState<string>('idle');

  // Load project list on mount
  useEffect(() => {
    loadProjects();
  }, []);

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

  const loadProjects = async () => {
    try {
      const data = await fetchProjects();
      setProjects(data);
      if (data.length > 0 && !selectedProject) {
        setSelectedProject(data[0]);
      }
    } catch (err) {
      console.error('Failed to load projects', err);
    }
  };

  const handleCreateProject = async (payload: CreateProjectPayload) => {
    const newProj = await createProject(payload);
    await loadProjects();
    setSelectedProject(newProj);
  };

  const handleGenerate = async () => {
    if (!selectedProject) return;
    try {
      await generateProject(selectedProject.name);
      const refreshedProject = await refreshProject(selectedProject.name);
      setSelectedProject(refreshedProject);
      setProjects((currentProjects) =>
        currentProjects.map((project) =>
          project.name === refreshedProject.name ? refreshedProject : project,
        ),
      );
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
    setProjects((currentProjects) =>
      currentProjects.map((project) =>
        project.name === refreshedProject.name ? refreshedProject : project,
      ),
    );
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.appTitle}>🦉 Hulotte GUI - StreamPU & SystemVerilog Dashboard</h1>
      </header>

      <div style={styles.grid}>
        <div style={styles.column}>
          <ProjectPanel
            projects={projects}
            selectedProject={selectedProject}
            onSelectProject={(p) => setSelectedProject(p)}
            onCreateProject={handleCreateProject}
          />
          <ActionsPanel
            project={selectedProject}
            onGenerate={handleGenerate}
            onBuild={handleBuild}
            onRun={handleRun}
            onStop={handleStop}
            status={status}
          />
        </div>

        <div style={styles.column}>
          <PipelinePanel project={selectedProject} />
          <ConsolePanel logs={logs} onClear={() => setLogs([])} />
        </div>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '24px',
    boxSizing: 'border-box',
  },
  header: {
    marginBottom: '24px',
    borderBottom: '1px solid #334155',
    paddingBottom: '16px',
  },
  appTitle: {
    margin: 0,
    fontSize: '1.5rem',
    color: '#f8fafc',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '24px',
  },
  column: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
};
