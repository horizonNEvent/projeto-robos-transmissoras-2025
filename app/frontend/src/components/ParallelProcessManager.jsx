import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './ParallelProcessManager.css';

import { ROBOTS } from '../constants/robots';

const ParallelProcessManager = ({ apiBaseUrl }) => {
    const [processes, setProcesses] = useState([]);
    const [showModal, setShowModal] = useState(false);
    const [loading, setLoading] = useState(false);
    const [logModal, setLogModal] = useState({ show: false, content: '', title: '' });

    const [robotConfigs, setRobotConfigs] = useState([]);
    const [selectedConfigIds, setSelectedConfigIds] = useState([]);
    const [showSuggestions, setShowSuggestions] = useState(false);

    // Estado do formulário de novo robô
    const [newRobot, setNewRobot] = useState({
        robot_name: 'siget',
        user: '',
        password: '',
        competencia: '',
        empresa: '',
        agente: '',
        headless: true
    });

    const ROBOT_OPTIONS = ROBOTS.map(r => ({
        value: r.id,
        label: r.name
    })).sort((a, b) => a.label.localeCompare(b.label));


    const fetchProcesses = async () => {
        try {
            const response = await axios.get(`${apiBaseUrl}/manager/list`);
            setProcesses(response.data);
        } catch (error) {
            console.error("Erro ao buscar processos:", error);
        }
    };

    const fetchConfigs = async () => {
        try {
            const res = await axios.get(`${apiBaseUrl}/config/robots`);
            setRobotConfigs(res.data);
        } catch (e) { console.error(e); }
    };

    useEffect(() => {
        fetchProcesses();
        fetchConfigs();
        const interval = setInterval(fetchProcesses, 3000);
        return () => clearInterval(interval);
    }, []);

    // Recarrega as configurações quando abre a modal pra garantir que estão atualizadas
    useEffect(() => {
        if (showModal) {
            fetchConfigs();
        }
    }, [showModal]);

    // Filtra configs do robô selecionado de forma flexível (por tipo, rótulo ou base)
    const availableConfigs = robotConfigs.filter(c => {
        const search = (newRobot.robot_name || '').trim().toLowerCase();
        if (!search) return false;

        const type = (c.robot_type || '').trim().toLowerCase();
        const label = (c.label || '').trim().toLowerCase();
        const base = (c.base || '').trim().toLowerCase();

        // 1. Match pelo tipo do robô (id)
        if (type === search) return true;
        if (type.replace('web', '') === search.replace('web', '')) return true;

        // 2. Match pelo rótulo amigável (Label)
        if (label === search || label.includes(search)) return true;

        // 3. Match pela base (AETE, RE, etc)
        if (base === search) return true;

        // 4. Lógica especial para WebIE
        if (search.startsWith('webie') && type === 'WEBIE') return true;
        if (search === 'web_ie' && type === 'WEBIE') return true;

        return false;
    });

    const handleStartRobot = async () => {
        setLoading(true);
        try {
            if (selectedConfigIds.length > 0) {
                const updatedRequest = selectedConfigIds.map(id => {
                    return axios.post(`${apiBaseUrl}/manager/start`, {
                        robot_name: newRobot.robot_name,
                        process_id: id,
                        competencia: newRobot.competencia || undefined,
                        headless: newRobot.headless
                    });
                });

                await Promise.all(updatedRequest);

            } else {
                const payload = {
                    robot_name: newRobot.robot_name,
                    user: newRobot.user || undefined,
                    password: newRobot.password || undefined,
                    competencia: newRobot.competencia || undefined,
                    empresa: newRobot.empresa || undefined,
                    agente: newRobot.agente || undefined,
                    headless: newRobot.headless
                };

                await axios.post(`${apiBaseUrl}/manager/start`, payload);
            }

            await fetchProcesses();
            setShowModal(false);
            setSelectedConfigIds([]);
        } catch (e) {
            alert("Erro ao iniciar robô(s)");
        } finally {
            setLoading(false);
        }
    };

    const handleStop = async (id) => {
        if (!window.confirm("Deseja realmente parar este robô?")) return;
        try {
            await axios.post(`${apiBaseUrl}/manager/stop/${id}`);
            await fetchProcesses();
        } catch (e) {
            console.error(e);
        }
    };

    const handleClear = async () => {
        try {
            await axios.delete(`${apiBaseUrl}/manager/clear`);
            await fetchProcesses();
        } catch (e) {
            console.error(e);
        }
    };


    const handleDownload = async (proc) => {
        try {
            const res = await axios.get(`${apiBaseUrl}/manager/download/${proc.id}`, {
                responseType: 'blob'
            });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `${proc.name}_${proc.id.slice(0, 8)}.zip`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            alert('Erro ao baixar arquivo');
        }
    };

    const handleDownloadAll = async () => {
        try {
            const res = await axios.get(`${apiBaseUrl}/manager/download-all`, {
                responseType: 'blob'
            });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `todos_robos.zip`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (e) {
            alert('Erro ao baixar todos os arquivos');
        }
    };

    const showLogs = async (proc) => {
        try {
            const res = await axios.get(`${apiBaseUrl}/manager/logs/${proc.id}`);
            const data = res.data;
            setLogModal({ show: true, content: data.logs, title: `${proc.name} Logs` });
        } catch (e) {
            alert("Erro ao buscar logs");
        }
    };

    const runningProcesses = processes.filter(p => p.status === 'running');
    const finishedProcesses = processes.filter(p => p.status !== 'running');

    return (
        <div className="process-manager-container">
            <div className="pm-header">
                <h2>Gerenciador de Robôs Paralelos</h2>
                <button className="btn-primary" onClick={() => setShowModal(true)}>➕ Novo Robô</button>
            </div>

            <div className="pm-section">
                <h3>Em Execução ({runningProcesses.length})</h3>
                <div className="process-list">
                    {runningProcesses.length === 0 && <p className="empty-msg">Nenhum robô rodando no momento.</p>}
                    {runningProcesses.map(p => (
                        <div key={p.id} className="process-card running">
                            <div className="pc-header">
                                <strong>{p.base_name ? `${p.name} - ${p.base_name}` : p.name}</strong>
                                <span className="status-badge running">RUNNING</span>
                            </div>
                            <div className="pc-details">
                                <small>ID: {p.id.slice(0, 8)}</small>
                                {p.agents && p.agents.length > 0 && (
                                    <small title={p.agents.join(', ')}>
                                        Agentes: {p.agents.slice(0, 3).join(', ')}{p.agents.length > 3 ? '...' : ''}
                                    </small>
                                )}
                                <small>Início: {new Date(p.start_time).toLocaleTimeString()}</small>
                            </div>
                            <div className="pc-actions">
                                <button onClick={() => showLogs(p)}>📜 Logs</button>
                                <button className="btn-danger" onClick={() => handleStop(p.id)}>⏹ Parar</button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="pm-section">
                <div className="pm-section-header">
                    <h3>Histórico / Finalizados ({finishedProcesses.length})</h3>
                    {finishedProcesses.length > 0 && (
                        <div>
                            <button className="btn-secondary" onClick={handleDownloadAll} style={{ marginRight: 10 }}>💾 Baixar Todos</button>
                            <button className="btn-secondary" onClick={handleClear}>🗑️ Limpar Histórico</button>
                        </div>
                    )}
                </div>
                <div className="process-list">
                    {finishedProcesses.length === 0 && <p className="empty-msg">Histórico vazio.</p>}
                    {finishedProcesses.map(p => (
                        <div key={p.id} className={`process-card ${p.status}`}>
                            <div className="pc-header">
                                <strong>{p.base_name ? `${p.name} - ${p.base_name}` : p.name}</strong>
                                <span className={`status-badge ${p.status}`}>{p.status.toUpperCase()}</span>
                            </div>
                            <div className="pc-details">
                                <small>Duração: {p.end_time ? ((new Date(p.end_time) - new Date(p.start_time)) / 1000).toFixed(1) + 's' : '-'}</small>
                                {p.agents && p.agents.length > 0 && (
                                    <small title={p.agents.join(', ')}>
                                        Agentes: {p.agents.slice(0, 3).join(', ')}{p.agents.length > 3 ? '...' : ''}
                                    </small>
                                )}
                                <small>Retorno: {p.return_code}</small>
                            </div>
                            <div className="pc-actions">
                                <button onClick={() => showLogs(p)}>📜 Logs</button>
                                <button className="btn-secondary" onClick={() => handleDownload(p)}>💾 Download</button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* MODAL DE NOVO ROBÔ */}
            {showModal && (
                <div className="modal-overlay">
                    <div className="modal-content">
                        <h3>Iniciar Novo Robô</h3>

                        <div className="form-group" style={{ position: 'relative' }}>
                            <label>Nome ou ID do Robô:</label>
                            <input
                                type="text"
                                className="form-control"
                                placeholder="Digite para buscar (ex: Glorian ou glorian)..."
                                value={newRobot.robot_name}
                                onChange={e => {
                                    setNewRobot({ ...newRobot, robot_name: e.target.value });
                                    setShowSuggestions(true);
                                    setSelectedConfigIds([]);
                                }}
                                onFocus={() => setShowSuggestions(true)}
                                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                                autoComplete="off"
                                style={{
                                    width: '100%', padding: '10px',
                                    backgroundColor: '#2a2a2a', border: '1px solid #444',
                                    color: '#fff', borderRadius: '4px'
                                }}
                            />

                            {showSuggestions && (
                                <ul style={{
                                    position: 'absolute', top: '100%', left: 0, right: 0,
                                    zIndex: 1000, background: '#252525', border: '1px solid #444',
                                    maxHeight: '200px', overflowY: 'auto', margin: 0, padding: 0, listStyle: 'none',
                                    boxShadow: '0 4px 8px rgba(0,0,0,0.5)',
                                    borderRadius: '0 0 4px 4px'
                                }}>
                                    {ROBOT_OPTIONS.filter(r =>
                                        r.label.toLowerCase().includes(newRobot.robot_name.toLowerCase()) ||
                                        r.value.toLowerCase().includes(newRobot.robot_name.toLowerCase())
                                    ).map(r => (
                                        <li
                                            key={r.value}
                                            onClick={() => {
                                                setNewRobot({ ...newRobot, robot_name: r.value });
                                                setShowSuggestions(false);
                                                setSelectedConfigIds([]);
                                            }}
                                            className="suggestion-item"
                                            style={{
                                                padding: '10px 12px', cursor: 'pointer', borderBottom: '1px solid #333',
                                                display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                                            }}
                                            onMouseEnter={(e) => e.currentTarget.style.background = '#3a3a3a'}
                                            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                                        >
                                            <span style={{ fontWeight: 500, color: '#e0e0e0' }}>{r.label}</span>
                                            <span style={{ color: '#888', fontSize: '0.85em', fontFamily: 'monospace' }}>{r.value}</span>
                                        </li>
                                    ))}
                                    {ROBOT_OPTIONS.filter(r => r.label.toLowerCase().includes(newRobot.robot_name.toLowerCase()) || r.value.toLowerCase().includes(newRobot.robot_name.toLowerCase())).length === 0 && newRobot.robot_name && (
                                        <li style={{ padding: '10px', color: '#aaa', fontStyle: 'italic', textAlign: 'center' }}>
                                            Nenhuma sugestão encontrada. Usando "{newRobot.robot_name}" como ID personalizado.
                                        </li>
                                    )}
                                </ul>
                            )}
                        </div>

                        {/* SELETOR DE PERFIS / EMPRESAS */}
                        {availableConfigs.length > 0 && (
                            <div className="form-group profiles-section" style={{ marginTop: '15px' }}>
                                <label style={{ color: '#84cc16', fontWeight: 'bold', fontSize: '1.1em' }}>✅ Perfis encontrados para "{newRobot.robot_name}":</label>
                                <div className="profiles-grid" style={{ marginTop: '10px' }}>
                                    {availableConfigs.map(config => (
                                        <div
                                            key={config.id}
                                            className={`profile-card ${selectedConfigIds.includes(config.id) ? 'selected' : ''}`}
                                            onClick={() => {
                                                setSelectedConfigIds(prev =>
                                                    prev.includes(config.id)
                                                        ? prev.filter(id => id !== config.id)
                                                        : [...prev, config.id]
                                                );
                                            }}
                                        >
                                            <div className="profile-name">{config.label || config.base}</div>
                                            <div className="profile-info">{JSON.parse(config.agents_json || '{}') ? Object.keys(JSON.parse(config.agents_json || '{}')).length + ' agentes' : 'S/ Agentes'}</div>
                                            {selectedConfigIds.includes(config.id) && <div className="check-icon">✓</div>}
                                        </div>
                                    ))}
                                </div>
                                <div className="profiles-actions">
                                    <small onClick={() => setSelectedConfigIds(availableConfigs.map(c => c.id))} style={{ cursor: 'pointer', color: '#aaa', marginRight: 10 }}>Selecionar Todos</small>
                                    <small onClick={() => setSelectedConfigIds([])} style={{ cursor: 'pointer', color: '#aaa' }}>Limpar</small>
                                </div>
                            </div>
                        )}

                        {/* FORMULARIO MANUAL (SÓ MOSTRA SE NENHUM PERFIL SELECIONADO) */}
                        {selectedConfigIds.length === 0 && (
                            <div className="manual-form">
                                <div style={{ borderTop: '1px solid #444', paddingTop: 10, marginTop: 10, fontSize: '0.9rem', color: '#aaa', fontStyle: 'italic', marginBottom: 10 }}>
                                    Preenchimento Manual (Opcional se não houver perfil)
                                </div>
                                <div className="form-row">
                                    <div className="form-group">
                                        <label>Usuário:</label>
                                        <input type="text" value={newRobot.user} onChange={e => setNewRobot({ ...newRobot, user: e.target.value })} />
                                    </div>
                                    <div className="form-group">
                                        <label>Senha:</label>
                                        <input type="password" value={newRobot.password} onChange={e => setNewRobot({ ...newRobot, password: e.target.value })} />
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="form-row">
                            <div className="form-group">
                                <label>Competência (MM/AAAA) <small>(Vazio = Mês Atual)</small>:</label>
                                <input type="text" placeholder="Ex: 01/2025" value={newRobot.competencia} onChange={e => setNewRobot({ ...newRobot, competencia: e.target.value })} />
                            </div>
                            <div className="form-group checkbox-group">
                                <label>
                                    <input type="checkbox" checked={newRobot.headless} onChange={e => setNewRobot({ ...newRobot, headless: e.target.checked })} />
                                    Modo Oculto (Headless)
                                </label>
                            </div>
                        </div>

                        <div className="modal-actions">
                            <button onClick={() => setShowModal(false)}>Cancelar</button>
                            <button className="btn-primary" onClick={handleStartRobot} disabled={loading}>
                                {loading
                                    ? 'Iniciando...'
                                    : (selectedConfigIds.length > 0 ? `▶️ Iniciar ${selectedConfigIds.length} Robôs` : '▶️ Iniciar')
                                }
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* MODAL DE LOGS */}
            {logModal.show && (
                <div className="modal-overlay" onClick={() => setLogModal({ show: false, content: '' })}>
                    <div className="modal-content modal-logs" onClick={e => e.stopPropagation()}>
                        <h3>{logModal.title}</h3>
                        <pre className="logs-viewer">{logModal.content}</pre>
                        <button onClick={() => setLogModal({ show: false, content: '' })}>Fechar</button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ParallelProcessManager;
