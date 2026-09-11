export interface ProjectManifest {
  schema_version: number;
  project: {
    name: string;
    root: string;
  };
  features: {
    streampu: boolean;
    aff3ct: boolean;
    custom: boolean;
    hardware: boolean;
    uart_io: boolean;
  };
  uart?: {
    enabled: boolean;
    port: string;
    baud: number;
    frame_size: number;
  };
  pipeline: {
    mode: 'minimal' | 'hw_only' | 'uart_only' | 'co_simulation';
  };
}

export interface ProjectData {
  name: string;
  path: string;
  manifest: ProjectManifest;
  status: 'idle' | 'building' | 'running' | 'error';
  pipeline_nodes?: string[];
}

export interface CreateProjectPayload {
  name: string;
  use_streampu: boolean;
  use_aff3ct: boolean;
  use_custom: boolean;
  use_hw: boolean;
  use_uart_io: boolean;
  uart_port?: string;
  uart_baud?: number;
  uart_frame_size?: number;
}

const API_BASE = '/api';

export async function fetchProjects(): Promise<ProjectData[]> {
  const res = await fetch(`${API_BASE}/projects`);
  if (!res.ok) throw new Error('Failed to fetch projects');
  return res.json();
}

export async function fetchProject(name: string): Promise<ProjectData> {
  const res = await fetch(`${API_BASE}/projects/${name}`);
  if (!res.ok) throw new Error(`Project ${name} not found`);
  return res.json();
}

export async function createProject(payload: CreateProjectPayload): Promise<ProjectData> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to create project');
  }
  const data = await res.json();
  return data.project;
}

export async function generateProject(name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${name}/generate`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to generate project');
}

export async function buildProject(name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${name}/build`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to start build');
}

export async function runProject(name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${name}/run`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to start execution');
}

export async function stopProject(name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${name}/stop`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop process');
}

export async function fetchProjectStatus(name: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/projects/${name}/status`);
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
}

export async function fetchProjectLogs(name: string): Promise<{ logs: string[] }> {
  const res = await fetch(`${API_BASE}/projects/${name}/logs`);
  if (!res.ok) throw new Error('Failed to fetch logs');
  return res.json();
}
