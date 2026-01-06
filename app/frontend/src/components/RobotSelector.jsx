function RobotSelector({ show, onClose, robots, selectedRobot, onSelect, search, onSearchChange }) {
    if (!show) return null

    return (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ background: '#1c1c1c', padding: '2rem', borderRadius: '15px', width: '90%', maxWidth: '500px', border: '1px solid #333' }}>
                <h3 style={{ marginTop: 0 }}>Selecionar Robô</h3>
                <input
                    type="text"
                    placeholder="Buscar robô..."
                    value={search}
                    onChange={(e) => onSearchChange(e.target.value)}
                    style={{ width: '100%', padding: '0.8rem', background: '#222', border: '1px solid #444', color: 'white', marginBottom: '1rem', borderRadius: '8px' }}
                />
                <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                    {robots.filter(r => r.name.toLowerCase().includes(search.toLowerCase())).map(r => (
                        <div
                            key={r.id}
                            onClick={() => { onSelect(r.id); onClose(); }}
                            style={{
                                padding: '1rem',
                                borderBottom: '1px solid #333',
                                cursor: 'pointer',
                                background: selectedRobot === r.id ? '#333' : 'transparent',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between'
                            }}
                            className="robot-item-hover"
                        >
                            <span>{r.name}</span>
                            {r.type === 'ie' && <small style={{ color: '#aaa', fontSize: '0.7em', border: '1px solid #444', padding: '2px 5px', borderRadius: '4px' }}>IE</small>}
                        </div>
                    ))}
                </div>
                <button
                    onClick={onClose}
                    style={{ width: '100%', marginTop: '1.5rem', padding: '0.8rem', background: '#333', border: 'none', color: 'white', cursor: 'pointer', borderRadius: '8px' }}
                >
                    Fechar
                </button>
            </div>
        </div>
    )
}

export default RobotSelector
