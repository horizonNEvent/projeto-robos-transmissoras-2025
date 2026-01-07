import { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = `http://${window.location.hostname}:8000`

function RobotConfigManager({ transmissoras = [], empresasMapping = {}, configs = [], onUpdate, forcedRobotType = null }) {
    const [editingConfigs, setEditingConfigs] = useState([])
    const [expandedId, setExpandedId] = useState(null)

    // Filtra configs baseadas no tipo forçado se existir
    const filteredConfigs = forcedRobotType
        ? configs.filter(c => c.robot_type.toUpperCase() === forcedRobotType.toUpperCase())
        : configs

    useEffect(() => {
        setEditingConfigs(filteredConfigs)
    }, [configs, forcedRobotType])

    // Model para nova config
    const [newConfig, setNewConfig] = useState({
        robot_type: forcedRobotType || 'SIGET',
        base: 'AETE',
        label: '',
        username: '',
        password: '',
        agents_json: '{}'
    })

    useEffect(() => {
        if (forcedRobotType) {
            setNewConfig(prev => ({ ...prev, robot_type: forcedRobotType }))
        }
    }, [forcedRobotType])

    // Campos temporários para adicionar agente
    const [newAgentCode, setNewAgentCode] = useState('')
    const [newAgentName, setNewAgentName] = useState('')

    const flatAgents = Object.entries(empresasMapping).flatMap(([group, agents]) =>
        Object.entries(agents).map(([code, name]) => ({ code, name, group }))
    )

    useEffect(() => {
        onUpdate()
    }, [])

    useEffect(() => {
        const code = newAgentCode.trim()
        if (code) {
            const found = flatAgents.find(a => String(a.code) === code) || transmissoras.find(t => String(t.codigo_ons) === code)
            if (found) {
                setNewAgentName(found.nome || found.name)
            }
        }
    }, [newAgentCode, flatAgents, transmissoras])

    const handleCreate = async () => {
        if (!newConfig.label) {
            alert("Informe um rótulo para a credencial")
            return
        }
        try {
            await axios.post(`${API_URL}/config/robots`, newConfig)
            onUpdate()
            setNewConfig({
                robot_type: forcedRobotType || 'SIGET',
                base: 'AETE',
                label: '',
                username: '',
                password: '',
                agents_json: '{}'
            })
        } catch (err) { alert(err.message) }
    }

    const handleSave = async (config) => {
        try {
            await axios.post(`${API_URL}/config/robots`, config)
            onUpdate()
            alert("Configuração salva!")
        } catch (err) { alert("Erro ao salvar: " + err.message) }
    }

    const handleDelete = async (id) => {
        if (!confirm("Excluir esta configuração?")) return
        try {
            await axios.delete(`${API_URL}/config/robots/${id}`)
            onUpdate()
        } catch (err) { alert(err.message) }
    }

    const updateConfigField = (id, field, value) => {
        setEditingConfigs(prev => prev.map(c => c.id === id ? { ...c, [field]: value } : c))
    }

    const addAgent = (id) => {
        if (!newAgentCode.trim() || !newAgentName.trim()) return
        const config = editingConfigs.find(c => c.id === id)
        if (!config) return
        let agents = {}
        try {
            agents = JSON.parse(config.agents_json || '{}') || {}
        } catch (e) { agents = {} }

        agents[newAgentCode.trim()] = newAgentName.trim()
        updateConfigField(id, 'agents_json', JSON.stringify(agents))
        setNewAgentCode('')
        setNewAgentName('')
    }

    const removeAgent = (id, code) => {
        const config = editingConfigs.find(c => c.id === id)
        if (!config) return
        let agents = {}
        try {
            agents = JSON.parse(config.agents_json || '{}') || {}
        } catch (e) { agents = {} }

        delete agents[code]
        updateConfigField(id, 'agents_json', JSON.stringify(agents))
    }

    return (
        <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3>⚙️ {forcedRobotType ? `Processos para ${forcedRobotType}` : 'Central de Configurações e Acessos'}</h3>
                <button onClick={onUpdate} style={{ background: 'transparent', border: '1px solid #444', padding: '0.4rem 0.8rem' }}>🔄 Atualizar</button>
            </div>

            <p style={{ fontSize: '0.9em', color: '#aaa', marginBottom: '1rem' }}>
                Gerencie aqui as credenciais de acesso e quais agentes/transmissoras cada uma deve processar.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {editingConfigs.map(c => (
                    <div key={c.id} style={{ border: '1px solid #444', borderRadius: '8px', overflow: 'hidden' }}>
                        <div
                            onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
                            style={{ background: '#333', padding: '1rem', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                        >
                            <div>
                                <span style={{ fontWeight: 'bold' }}>{c.label}</span>
                                <span style={{ fontSize: '0.7em', background: '#555', padding: '2px 5px', borderRadius: '4px', marginLeft: '10px' }}>{c.robot_type}</span>
                                <span style={{ fontSize: '0.7em', background: '#2980b9', padding: '2px 5px', borderRadius: '4px', marginLeft: '5px' }}>{c.base}</span>
                            </div>
                            <span style={{ color: '#aaa', fontSize: '0.8em' }}>
                                {(() => {
                                    try {
                                        return Object.keys(JSON.parse(c.agents_json || '{}') || {}).length
                                    } catch (e) { return 0 }
                                })()} agentes | {expandedId === c.id ? '▼' : '▶'}
                            </span>
                        </div>

                        {expandedId === c.id && (
                            <div style={{ padding: '1rem', background: '#222' }}>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', marginBottom: '1rem' }}>
                                    <div>
                                        <label style={{ fontSize: '0.75em', color: '#888' }}>Rótulo / Nome</label>
                                        <input value={c.label} onChange={e => updateConfigField(c.id, 'label', e.target.value)} style={{ width: '100%', background: '#111', border: '1px solid #444', color: '#fff', padding: '5px' }} />
                                    </div>
                                    <div>
                                        <label style={{ fontSize: '0.75em', color: '#888' }}>Usuário / E-mail</label>
                                        <input value={c.username} onChange={e => updateConfigField(c.id, 'username', e.target.value)} style={{ width: '100%', background: '#111', border: '1px solid #444', color: '#fff', padding: '5px' }} />
                                    </div>
                                    <div>
                                        <label style={{ fontSize: '0.75em', color: '#888' }}>Senha</label>
                                        <input type="password" value={c.password} onChange={e => updateConfigField(c.id, 'password', e.target.value)} style={{ width: '100%', background: '#111', border: '1px solid #444', color: '#fff', padding: '5px' }} />
                                    </div>
                                </div>

                                <h4 style={{ borderBottom: '1px solid #444', paddingBottom: '5px', marginBottom: '10px' }}>Agentes Vinculados</h4>
                                <div style={{ maxHeight: '200px', overflowY: 'auto', marginBottom: '10px', background: '#1b1b1b', borderRadius: '4px' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85em' }}>
                                        <thead>
                                            <tr style={{ background: '#252525', textAlign: 'left', color: '#888' }}>
                                                <th style={{ padding: '5px' }}>ONS</th>
                                                <th style={{ padding: '5px' }}>Agente</th>
                                                <th style={{ padding: '5px', width: '30px' }}></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {(() => {
                                                try {
                                                    const agents = JSON.parse(c.agents_json || '{}') || {}
                                                    return Object.entries(agents).map(([code, name]) => (
                                                        <tr key={code} style={{ borderBottom: '1px solid #333' }}>
                                                            <td style={{ padding: '5px', fontFamily: 'monospace' }}>{code}</td>
                                                            <td style={{ padding: '5px' }}>{name}</td>
                                                            <td style={{ textAlign: 'right', padding: '5px' }}>
                                                                <button onClick={() => removeAgent(c.id, code)} style={{ background: 'none', border: 'none', color: '#e74c3c', cursor: 'pointer' }}>✖</button>
                                                            </td>
                                                        </tr>
                                                    ))
                                                } catch (e) { return null }
                                            })()}
                                        </tbody>
                                    </table>
                                </div>

                                <div style={{ display: 'flex', gap: '5px', marginBottom: '1.5rem', background: '#333', padding: '5px', borderRadius: '4px' }}>
                                    <input placeholder="Cód" list="master-agents" value={newAgentCode} onChange={e => setNewAgentCode(e.target.value)} style={{ width: '80px', background: '#111', border: '1px solid #555', color: '#fff' }} />
                                    <input placeholder="Nome do Agente" value={newAgentName} onChange={e => setNewAgentName(e.target.value)} onKeyDown={e => e.key === 'Enter' && addAgent(c.id)} style={{ flex: 1, background: '#111', border: '1px solid #555', color: '#fff' }} />
                                    <button onClick={() => addAgent(c.id)} style={{ background: '#2980b9' }}>+ Adicionar</button>
                                </div>

                                <div style={{ display: 'flex', gap: '10px' }}>
                                    <button onClick={() => handleSave(c)} style={{ flex: 1, background: '#27ae60', padding: '0.6rem' }}>💾 Salvar Alterações</button>
                                    <button onClick={() => handleDelete(c.id)} style={{ background: '#c0392b', padding: '0.6rem' }}>🗑️ Excluir</button>
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>

            <div style={{ marginTop: '2.5rem', borderTop: '1px solid #444', paddingTop: '1.5rem' }}>
                <h4 style={{ marginBottom: '1rem' }}>➕ Criar Nova Credencial</h4>
                <div style={{ display: 'grid', gridTemplateColumns: forcedRobotType ? '1fr 1fr' : '1fr 1fr 1fr', gap: '10px', marginBottom: '10px' }}>
                    {!forcedRobotType && (
                        <div>
                            <label style={{ fontSize: '0.7em', color: '#888' }}>Tipo de Robô</label>
                            <select value={newConfig.robot_type} onChange={e => setNewConfig({ ...newConfig, robot_type: e.target.value })} style={{ width: '100%', background: '#333', color: '#fff', padding: '5px' }}>
                                <option value="SIGET">WebSiget</option>
                                <option value="WEBIE">WebIERIACHOGRANDE</option>
                            </select>
                        </div>
                    )}
                    <div>
                        <label style={{ fontSize: '0.7em', color: '#888' }}>Base</label>
                        <select value={newConfig.base} onChange={e => setNewConfig({ ...newConfig, base: e.target.value })} style={{ width: '100%', background: '#333', color: '#fff', padding: '5px' }}>
                            {['AETE', 'RE', 'AE', 'DE'].map(b => <option key={b} value={b}>{b}</option>)}
                        </select>
                    </div>
                    <div>
                        <label style={{ fontSize: '0.7em', color: '#888' }}>Rótulo Amigável</label>
                        <input placeholder="ex: Anemus 1" value={newConfig.label} onChange={e => setNewConfig({ ...newConfig, label: e.target.value })} style={{ width: '100%', background: '#333', color: '#fff', padding: '5px' }} />
                    </div>
                </div>
                <button onClick={handleCreate} style={{ width: '100%', background: '#2980b9', padding: '0.8rem', borderRadius: '4px', fontWeight: 'bold' }}>Criar Credencial</button>
            </div>

            <datalist id="master-agents">
                {flatAgents.map(a => (
                    <option key={`${a.group}-${a.code}`} value={a.code}>{`[${a.group}] ${a.name}`}</option>
                ))}
            </datalist>
        </div>
    )
}

export default RobotConfigManager
