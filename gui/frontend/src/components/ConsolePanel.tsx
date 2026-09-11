import React, { useEffect, useRef } from 'react';

interface ConsolePanelProps {
  logs: string[];
  onClear: () => void;
}

export const ConsolePanel: React.FC<ConsolePanelProps> = ({ logs, onClear }) => {
  const terminalRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs.length]);

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <h2 style={styles.title}>💻 Console Output</h2>
        <button style={styles.clearBtn} onClick={onClear}>
          Effacer
        </button>
      </div>

      <div ref={terminalRef} style={styles.terminal}>
        {logs.length === 0 ? (
          <span style={styles.empty}>Aucun log pour le moment...</span>
        ) : (
          logs.map((line, index) => (
            <div key={index} style={styles.logLine}>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  card: {
    backgroundColor: '#1e293b',
    borderRadius: '8px',
    padding: '16px',
    border: '1px solid #334155',
    display: 'flex',
    flexDirection: 'column',
    height: '300px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  title: {
    margin: 0,
    fontSize: '1.2rem',
    color: '#38bdf8',
  },
  clearBtn: {
    backgroundColor: '#475569',
    color: '#f8fafc',
    border: 'none',
    padding: '4px 8px',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '0.8rem',
  },
  terminal: {
    backgroundColor: '#020617',
    borderRadius: '6px',
    padding: '12px',
    flex: 1,
    overflowY: 'auto',
    fontFamily: 'Consolas, Monaco, "Andale Mono", "Ubuntu Mono", monospace',
    fontSize: '0.85rem',
    color: '#38bdf8',
    whiteSpace: 'pre-wrap',
    border: '1px solid #0f172a',
  },
  empty: {
    color: '#64748b',
    fontStyle: 'italic',
  },
  logLine: {
    lineHeight: '1.4',
  },
};
