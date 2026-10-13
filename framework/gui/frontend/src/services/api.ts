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

export interface PipelineNode {
  name: string;
  type: string;
  id?: string;
  enabled?: boolean;
  generic?: boolean;
  // Optional manifest fields, present depending on module kind (custom/hardware/uart_wrapped)
  module_name?: string;
  class_name?: string;
  kind?: string;
  source?: string;
  header?: string;
  wrapper_source?: string;
  core_source?: string;
}

export interface ProjectData {
  name: string;
  path: string;
  manifest: ProjectManifest;
  status: 'idle' | 'building' | 'running' | 'error';
  pipeline_nodes?: PipelineNode[];
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

export interface ProjectValidationResult {
  valid: boolean;
  manifest: string;
  errors: string[];
}

export interface GraphPaletteEntry {
  catalog_id: string;
  kind: string;
  label: string;
  family: string;
  description: string;
  parameters: unknown[];
  ports: Record<string, unknown>;
}

export interface GraphPayload {
  modules: Record<string, any>;
  connections: Array<{ from: string; to: string }>;
}

export interface GraphValidationResult {
  valid: boolean;
  payload?: GraphPayload;
  error?: string;
}

const API_BASE = window.location.protocol === 'file:'
  ? 'http://127.0.0.1:8000/api'
  : '/api';

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

export async function openProjectFile(name: string, path: string): Promise<{ path: string }> {
  const res = await fetch(`${API_BASE}/projects/${name}/open-file`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Impossible d\'ouvrir le fichier');
  }
  return res.json();
}

export async function createProject(payload: CreateProjectPayload): Promise<ProjectData> {
  if (!/^[A-Za-z_][A-Za-z0-9_-]*$/.test(payload.name)) {
    throw new Error('Le nom du projet doit commencer par une lettre ou un underscore et ne contenir que des lettres, chiffres, underscores ou tirets.');
  }
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
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail?.errors?.join('\n') || error.detail || 'Failed to validate project');
  }
}

export async function refreshProject(name: string): Promise<ProjectData> {
  const res = await fetch(`${API_BASE}/projects/${name}`);
  if (!res.ok) throw new Error(`Project ${name} not found`);
  return res.json();
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

export async function fetchGraphPalette(): Promise<GraphPaletteEntry[]> {
  const res = await fetch(`${API_BASE}/graph/palette`);
  if (!res.ok) throw new Error('Failed to fetch graph palette');
  return res.json();
}

export async function addGraphBlock(payload: {
  catalog_id: string;
  block_id?: string;
  x?: number;
  y?: number;
  task?: string;
  canvas?: GraphPayload;
}): Promise<{ block: any; canvas: GraphPayload }> {
  const res = await fetch(`${API_BASE}/graph/blocks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to add graph block');
  }
  return res.json();
}

export async function connectGraphBlocks(payload: {
  source_block: string;
  source_task: string;
  source_port: string;
  target_block: string;
  target_task: string;
  target_port: string;
  canvas?: GraphPayload;
}): Promise<{ connection: any; canvas: GraphPayload }> {
  const res = await fetch(`${API_BASE}/graph/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to connect blocks');
  }
  return res.json();
}

export async function validateGraph(graph: GraphPayload): Promise<GraphValidationResult> {
  const res = await fetch(`${API_BASE}/graph/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(graph),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Graph validation failed');
  }
  return res.json();
}

export async function saveProjectGraph(name: string, graph: GraphPayload): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(name)}/graph`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(graph),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Impossible d\'enregistrer le graphe');
  }
}
