function LogsPanel({ logs }) {
    return (
        <div className="logs-container">
            {logs.length === 0 ? (
                <div style={{ color: '#64748b', padding: '1rem', fontStyle: 'italic' }}>
                    Sem atividades recentes...
                </div>
            ) : (
                logs.map((log, i) => {
                    // Extrai o tempo entre [] para dar cor
                    const timeMatch = log.match(/^\[(.*?)\] (.*)/);
                    if (timeMatch) {
                        return (
                            <div key={i} className="log-line">
                                <span className="log-time">[{timeMatch[1]}]</span>
                                <span>{timeMatch[2]}</span>
                            </div>
                        );
                    }
                    return <div key={i} className="log-line">{log}</div>;
                })
            )}
        </div>
    )
}

export default LogsPanel
