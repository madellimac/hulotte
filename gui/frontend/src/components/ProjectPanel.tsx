import React, { useState } from 'react';
import { ProjectData, CreateProjectPayload } from '../services/api';

interface ProjectPanelProps {
  projects: ProjectData[];
  selectedProject: ProjectData | null;
  onSelectProject: (project: ProjectData) => void;
  onCreateProject: (payload: CreateProjectPayload) => Promise<void>;
}

export const ProjectPanel: React.FC<ProjectPanelProps> = ({
  projects,
  selectedProject,
  onSelectProject,
  onCreateProject,
}) => {
  const [isCreating, setIsCreating] = useState(false);
  const [formData, setFormData] = useState<CreateProjectPayload>({
    name: '',
    use_streampu: true,
    use_aff3ct: false,
    use_custom: true,
    use_hw: false,
    use_uart_io: false,
    uart_port: '/dev/ttyUSB0',
    uart_baud: 115200,
    uart_frame_size: 16,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    try {
      await onCreateProject(formData);
      setIsCreating(false);
      setFormData({ ...formData, name: '' });
    } catch (err: any) {
      alert(err.message || 'Erreur lors de la création du projet');
    }
  };

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <h2 style={styles.title}>📌 Projet Hulotte</h2>
        <button
          style={styles.toggleBtn}
          onClick={() => setIsCreating(!isCreating)}
        >
          {isCreating ? 'Annuler' : '+ Nouveau Projet'}
        </button>
      </div>

      {isCreating ? (
        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.field}>
            <label style={styles.label}>Nom du Projet :</label>
            <input
              type="text"
              style={styles.input}
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="ex: my_hulotte_app"
              required
            />
          </div>

          <div style={styles.checkboxGroup}>
            <label style={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={formData.use_streampu}
                onChange={(e) => setFormData({ ...formData, use_streampu: e.target.checked })}
              />
              StreamPU (Dataflow)
            </label>
            <label style={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={formData.use_aff3ct}
                onChange={(e) => setFormData({ ...formData, use_aff3ct: e.target.checked })}
              />
              AFF3CT (Codage Canal)
            </label>
            <label style={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={formData.use_custom}
                onChange={(e) => setFormData({ ...formData, use_custom: e.target.checked })}
              />
              Custom Module (C++)
            </label>
            <label style={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={formData.use_hw}
                onChange={(e) => setFormData({ ...formData, use_hw: e.target.checked })}
              />
              Hardware (Verilator SystemVerilog)
            </label>
            <label style={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={formData.use_uart_io}
                onChange={(e) => setFormData({ ...formData, use_uart_io: e.target.checked })}
              />
              UART I/O (FPGA)
            </label>
          </div>

          <button type="submit" style={styles.submitBtn}>
            Créer le Projet
          </button>
        </form>
      ) : (
        <div>
          <div style={styles.field}>
            <label style={styles.label}>Sélectionner un projet :</label>
            <select
              style={styles.select}
              value={selectedProject?.name || ''}
              onChange={(e) => {
                const proj = projects.find((p) => p.name === e.target.value);
                if (proj) onSelectProject(proj);
              }}
            >
              <option value="" disabled>-- Choisir un projet --</option>
              {projects.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name} ({p.manifest.pipeline?.mode || 'minimal'})
                </option>
              ))}
            </select>
          </div>

          {selectedProject && (
            <div style={styles.infoBox}>
              <p><strong>Nom :</strong> {selectedProject.name}</p>
              <p><strong>Mode :</strong> <span style={styles.badge}>{selectedProject.manifest.pipeline?.mode || 'minimal'}</span></p>
              <p><strong>Fonctionnalités :</strong></p>
              <ul style={styles.featureList}>
                <li>StreamPU: {selectedProject.manifest.features.streampu ? '✅' : '❌'}</li>
                <li>AFF3CT: {selectedProject.manifest.features.aff3ct ? '✅' : '❌'}</li>
                <li>Custom C++: {selectedProject.manifest.features.custom ? '✅' : '❌'}</li>
                <li>Hardware (Verilator): {selectedProject.manifest.features.hardware ? '✅' : '❌'}</li>
                <li>UART I/O: {selectedProject.manifest.features.uart_io ? '✅' : '❌'}</li>
              </ul>
            </div>
          )}
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
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '16px',
  },
  title: {
    margin: 0,
    fontSize: '1.2rem',
    color: '#38bdf8',
  },
  toggleBtn: {
    backgroundColor: '#3b82f6',
    color: '#ffffff',
    border: 'none',
    padding: '6px 12px',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '0.85rem',
  },
  field: {
    marginBottom: '12px',
  },
  label: {
    display: 'block',
    fontSize: '0.85rem',
    color: '#94a3b8',
    marginBottom: '4px',
  },
  input: {
    width: '100%',
    padding: '8px',
    borderRadius: '4px',
    border: '1px solid #475569',
    backgroundColor: '#0f172a',
    color: '#f8fafc',
    boxSizing: 'border-box',
  },
  select: {
    width: '100%',
    padding: '8px',
    borderRadius: '4px',
    border: '1px solid #475569',
    backgroundColor: '#0f172a',
    color: '#f8fafc',
  },
  checkboxGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    margin: '12px 0',
  },
  checkboxLabel: {
    fontSize: '0.85rem',
    color: '#cbd5e1',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: 'pointer',
  },
  submitBtn: {
    backgroundColor: '#10b981',
    color: '#ffffff',
    border: 'none',
    padding: '8px 16px',
    borderRadius: '4px',
    cursor: 'pointer',
    width: '100%',
    fontWeight: 'bold',
  },
  infoBox: {
    marginTop: '12px',
    padding: '12px',
    backgroundColor: '#0f172a',
    borderRadius: '6px',
    fontSize: '0.85rem',
  },
  badge: {
    backgroundColor: '#0284c7',
    padding: '2px 8px',
    borderRadius: '12px',
    fontSize: '0.75rem',
  },
  featureList: {
    margin: '4px 0 0 0',
    paddingLeft: '20px',
    color: '#cbd5e1',
  },
};
