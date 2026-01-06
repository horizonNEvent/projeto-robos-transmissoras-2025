import { useState, useEffect } from 'react'
import axios from 'axios'
import './App.css' // Usando estilos default + index.css

const API_URL = "http://localhost:8000"

function App() {
  const [status, setStatus] = useState('idle') // idle, running, finished
  const [logs, setLogs] = useState([])
  const [downloadUrl, setDownloadUrl] = useState(null)
  const [empresas, setEmpresas] = useState([])
  const [selectedRobot, setSelectedRobot] = useState('siget')
  const [showRobotSelector, setShowRobotSelector] = useState(false)
  const [robotSearch, setRobotSearch] = useState('')
  // Definição dos Robôs
  const ROBOTS = [
    { id: 'siget', name: 'WebSiget' },
    { id: 'cnt', name: 'WebCnt' },
    { id: 'pantanal', name: 'WebPantanal' },
    { id: 'assu', name: 'WebAssu' },
    { id: 'tropicalia', name: 'WebTropicalia' },
    { id: 'firminopolis', name: 'WebFirminopolis' },
    { id: 'evoltz', name: 'WebEvoltz' },
    // Futuros robôs podem ser adicionados aqui
  ]
  // Definição dos Robôs

  const filteredRobots = ROBOTS.filter(r => r.name.toLowerCase().includes(robotSearch.toLowerCase()))

  // Estado para Edição/Criação
  const [formData, setFormData] = useState({ codigo_ons: '', nome_empresa: '', base: 'AETE' })
  const [editingId, setEditingId] = useState(null)

  // Estado Específico Siget
  const [sigetBase, setSigetBase] = useState('AETE')
  const [sigetEmail, setSigetEmail] = useState('tust@2wecobank.com.br')
  const [repoCreds, setRepoCreds] = useState({})

  useEffect(() => {
    fetchEmpresas()
    const savedCreds = localStorage.getItem('siget_creds')
    if (savedCreds) {
      setRepoCreds(JSON.parse(savedCreds))
    }
  }, [])

  // Atualiza email ao trocar de base (se houver salvo)
  useEffect(() => {
    if (repoCreds[sigetBase]) {
      setSigetEmail(repoCreds[sigetBase])
    }
  }, [sigetBase, repoCreds])

  const handleSaveSigetCreds = () => {
    const newCreds = { ...repoCreds, [sigetBase]: sigetEmail }
    setRepoCreds(newCreds)
    localStorage.setItem('siget_creds', JSON.stringify(newCreds))
    setLogs(prev => [...prev, `Credencial salva para ${sigetBase}`])
  }

  const fetchEmpresas = async () => {
    try {
      const res = await axios.get(`${API_URL}/empresas`)
      setEmpresas(res.data)
    } catch (err) {
      console.error("Erro ao buscar empresas", err)
    }
  }

  const syncEmpresas = async () => {
    try {
      await axios.post(`${API_URL}/empresas/sync`)
      fetchEmpresas()
    } catch (err) {
      console.error("Erro ao sincronizar", err)
    }
  }

  const handleRunRobot = async () => {
    setStatus('running')
    setDownloadUrl(null)
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Iniciando robô ${selectedRobot.toUpperCase()}...`])

    try {
      const payload = { robot_name: selectedRobot }

      if (selectedRobot === 'siget') {
        // Agora o backend lê o arquivo empresas.siget.json direto
        setLogs(prev => [...prev, `Usando configuração: params do servidor (empresas.siget.json)`])
      }

      await axios.post(`${API_URL}/run-robot`, payload)
      // Inicia polling
      pollStatus(selectedRobot)

    } catch (err) {
      setStatus('idle')
      setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Erro: ${err.message}`])
      if (err.response && err.response.data) {
        setLogs(prev => [...prev, `Detalhe: ${err.response.data.detail}`])
      }
    }
  }

  const pollStatus = async (robotName) => {
    try {
      const res = await axios.get(`${API_URL}/robot-status/${robotName}`)
      const currentStatus = res.data.status // 'idle', 'running', 'finished', 'error'

      if (currentStatus === 'finished') {
        setStatus('finished')
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Robô finalizou com sucesso!`])
        setDownloadUrl(`${API_URL}/download-results?robot=${robotName}`)
      } else if (currentStatus === 'error') {
        setStatus('idle')
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] Robô encontrou um erro. Verifique o servidor.`])
      } else {
        // Continua rodando, checa de novo em 2s
        setTimeout(() => pollStatus(robotName), 2000)
      }
    } catch (e) {
      console.error("Erro no polling", e)
      // Tenta de novo em 2s mesmo com erro de rede
      setTimeout(() => pollStatus(robotName), 2000)
    }
  }

  // CRUD Handlers
  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingId) {
        await axios.put(`${API_URL}/empresas/${editingId}`, formData)
        setLogs(prev => [...prev, `Empresa atualizada: ${formData.nome_empresa}`])
      } else {
        await axios.post(`${API_URL}/empresas`, formData)
        setLogs(prev => [...prev, `Nova empresa criada: ${formData.nome_empresa}`])
      }
      setFormData({ codigo_ons: '', nome_empresa: '', base: 'AETE' })
      setEditingId(null)
      fetchEmpresas()
    } catch (err) {
      console.error(err)
      alert("Erro ao salvar empresa")
    }
  }

  const handleEdit = (emp) => {
    setFormData({ codigo_ons: emp.codigo_ons, nome_empresa: emp.nome_empresa, base: emp.base })
    setEditingId(emp.id)
  }

  const handleDelete = async (id) => {
    if (!confirm("Tem certeza que deseja excluir?")) return
    try {
      await axios.delete(`${API_URL}/empresas/${id}`)
      setLogs(prev => [...prev, `Empresa excluída.`])
      fetchEmpresas()
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <>
      <header>
        <h1>🤖 AETE Robo Runner</h1>
        <p>Orquestrador de Automação TUST</p>
      </header>

      <div className="grid-layout">

        <div className="control-panel">
          <div className="card">
            <h2>Controle de Execução</h2>





            {/* Seletor de Robô (Botão que abre Modal) */}
            <div style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
              <button
                onClick={() => setShowRobotSelector(true)}
                style={{
                  padding: '0.8rem 1.5rem',
                  fontSize: '1em',
                  background: '#333',
                  border: '1px solid var(--accent)',
                  borderRadius: '8px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  cursor: 'pointer'
                }}
              >

                {ROBOTS.find(r => r.id === selectedRobot)?.name}
                <span style={{ fontSize: '0.8em', opacity: 0.7 }}>▼</span>
              </button>
            </div>



            <div className={`status-badge status-${status}`}>
              {status === 'idle' && 'AGUARDANDO'}
              {status === 'running' && 'EXECUTANDO...'}
              {status === 'finished' && 'FINALIZADO'}
            </div>

            <div style={{ marginTop: '2rem' }}>
              <button
                onClick={handleRunRobot}
                disabled={status === 'running'}
                style={{ width: '100%' }}
              >
                {status === 'running' ? 'Processando...' : `▶ Iniciar Robô ${selectedRobot.toUpperCase()}`}
              </button>
            </div>

            {downloadUrl && (
              <div style={{ marginTop: '1rem' }}>
                <a href={downloadUrl} target="_blank" rel="noreferrer">
                  <button style={{ backgroundColor: '#27ae60', width: '100%' }}>
                    ⬇ Baixar Resultados ({selectedRobot.toUpperCase()})
                  </button>
                </a>
              </div>
            )}
          </div>

          <div className="card" style={{ textAlign: 'left', maxHeight: '200px', overflowY: 'auto', position: 'relative', zIndex: 0 }}>
            <h3>Logs de Atividade</h3>
            <ul style={{ listStyle: 'none', padding: 0, fontSize: '0.9em', color: '#aaa' }}>
              {logs.map((log, i) => <li key={i}>{log}</li>)}
            </ul>
          </div>
        </div>

        <div className="data-panel">
          {selectedRobot === 'siget' ? (
            <SigetConfigPanel />
          ) : (
            <>
              <div className="card" style={{ marginBottom: '1rem' }}>
                <h3>{editingId ? 'Editar Empresa' : 'Adicionar Nova Empresa / Base'}</h3>
                <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <input
                    name="codigo_ons"
                    value={formData.codigo_ons}
                    onChange={handleInputChange}
                    placeholder="Cód. ONS (ex: 4284)"
                    required
                    style={{ padding: '0.5em', borderRadius: '4px', border: '1px solid #444', background: '#222', color: 'white' }}
                  />
                  <input
                    name="nome_empresa"
                    value={formData.nome_empresa}
                    onChange={handleInputChange}
                    placeholder="Nome Empresa"
                    required
                    style={{ flex: 1, padding: '0.5em', borderRadius: '4px', border: '1px solid #444', background: '#222', color: 'white' }}
                  />
                  <input
                    name="base"
                    value={formData.base}
                    onChange={handleInputChange}
                    placeholder="Base (ex: AETE)"
                    required
                    style={{ width: '80px', padding: '0.5em', borderRadius: '4px', border: '1px solid #444', background: '#222', color: 'white' }}
                  />
                  <button type="submit" style={{ padding: '0.5em 1em', fontSize: '0.9em' }}>
                    {editingId ? 'Salvar' : 'Adicionar'}
                  </button>
                  {editingId && (
                    <button type="button" onClick={() => { setEditingId(null); setFormData({ codigo_ons: '', nome_empresa: '', base: 'AETE' }) }} style={{ background: '#555' }}>
                      Cancelar
                    </button>
                  )}
                </form>
              </div>

              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3>Empresas Cadastradas</h3>
                  <button
                    onClick={syncEmpresas}
                    style={{ fontSize: '0.8em', padding: '0.5em', background: 'transparent', border: '1px solid #555' }}
                  >
                    🔄 Sincronizar DB
                  </button>
                </div>

                {empresas.length === 0 ? (
                  <p style={{ color: '#666' }}>Nenhuma empresa. Adicione ou sincronize.</p>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>ID ONS</th>
                        <th>Nome Empresa</th>
                        <th>Base</th>
                        <th>Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {empresas.map(emp => (
                        <tr key={emp.id}>
                          <td>{emp.codigo_ons}</td>
                          <td>{emp.nome_empresa}</td>
                          <td>
                            <span style={{
                              background: '#333',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '0.8em',
                              border: '1px solid #444'
                            }}>
                              {emp.base}
                            </span>
                          </td>
                          <td>
                            <button onClick={() => handleEdit(emp)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 5px', fontSize: '1.2em' }}>✏️</button>
                            <button onClick={() => handleDelete(emp.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 5px', fontSize: '1.2em' }}>🗑️</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}
        </div>
      </div >



      {/* Modal de Seleção de Robô - Movido para fora para garantir z-index global */}
      {
        showRobotSelector && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(0,0,0,0.8)',
            zIndex: 9999, // Z-index altíssimo
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center'
          }}>
            <div style={{
              background: '#1a1a1a',
              padding: '2rem',
              borderRadius: '12px',
              width: '90%',
              maxWidth: '400px',
              border: '1px solid #444',
              boxShadow: '0 10px 30px rgba(0,0,0,0.5)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0 }}>Selecionar Robô</h3>
                <button onClick={() => setShowRobotSelector(false)} style={{ background: 'none', border: 'none', fontSize: '1.5em', cursor: 'pointer' }}>×</button>
              </div>

              <input
                type="text"
                placeholder="🔍 Buscar Robô..."
                value={robotSearch}
                onChange={e => setRobotSearch(e.target.value)}
                autoFocus
                style={{
                  width: '100%',
                  padding: '0.8rem',
                  marginBottom: '1rem',
                  background: '#333',
                  border: '1px solid #444',
                  borderRadius: '6px',
                  color: 'white'
                }}
              />

              <div style={{ maxHeight: '60vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {filteredRobots.map(robot => (
                  <button
                    key={robot.id}
                    onClick={() => { setSelectedRobot(robot.id); setShowRobotSelector(false); }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1rem',
                      padding: '1rem',
                      backgroundColor: selectedRobot === robot.id ? 'var(--accent)' : '#2a2a2a',
                      border: selectedRobot === robot.id ? '1px solid var(--accent)' : '1px solid #444',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      textAlign: 'left'
                    }}
                  >
                    <span style={{ fontWeight: 'bold' }}>{robot.name}</span>
                  </button>
                ))}
                {filteredRobots.length === 0 && <p style={{ color: '#888', textAlign: 'center' }}>Nenhum robô encontrado.</p>}
              </div>
            </div>
          </div>
        )
      }
    </>
  )
}

function SigetConfigPanel() {
  const [config, setConfig] = useState({})
  const [loading, setLoading] = useState(false)
  const [expandedBase, setExpandedBase] = useState(null)
  const [newBaseName, setNewBaseName] = useState('')

  // Campos temporários para adicionar agente
  const [newAgentCode, setNewAgentCode] = useState('')
  const [newAgentName, setNewAgentName] = useState('')

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_URL}/siget-config`)
      // Normaliza agentes para objeto se estiver como array
      const data = res.data || {}
      for (const key in data) {
        if (data[key].agentes && Array.isArray(data[key].agentes)) {
          const dict = {}
          data[key].agentes.forEach(item => {
            // Assume que o item é { key: value }
            const k = Object.keys(item)[0]
            dict[k] = item[k]
          })
          data[key].agentes = dict
        }
      }
      setConfig(data)
    } catch (err) {
      console.error("Erro ao buscar config Siget", err)
      setConfig({})
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      await axios.post(`${API_URL}/siget-config`, config)
      alert("Configuração salva com sucesso!")
    } catch (err) {
      alert("Erro ao salvar: " + err.message)
    }
  }

  // --- Actions ---

  const addBase = () => {
    const name = newBaseName.trim()
    if (!name) return
    if (config[name]) {
      alert("Essa base já existe!")
      return
    }
    setConfig(prev => ({
      ...prev,
      [name]: { email: '', agentes: {} }
    }))
    setNewBaseName('')
    setExpandedBase(name)
  }

  const removeBase = (base) => {
    if (!confirm(`Tem certeza que deseja excluir a base ${base}?`)) return
    const newConfig = { ...config }
    delete newConfig[base]
    setConfig(newConfig)
    if (expandedBase === base) setExpandedBase(null)
  }

  const updateEmail = (base, email) => {
    setConfig(prev => ({
      ...prev,
      [base]: { ...prev[base], email: email }
    }))
  }

  const addAgent = (base) => {
    if (!newAgentCode.trim() || !newAgentName.trim()) return
    setConfig(prev => ({
      ...prev,
      [base]: {
        ...prev[base],
        agentes: {
          ...prev[base].agentes,
          [newAgentCode.trim()]: newAgentName.trim()
        }
      }
    }))
    setNewAgentCode('')
    setNewAgentName('')
  }

  const removeAgent = (base, code) => {
    const newConfig = { ...config }
    // Shallow copy do objeto da base e agentes para imutabilidade
    newConfig[base] = { ...newConfig[base] }
    newConfig[base].agentes = { ...newConfig[base].agentes }

    delete newConfig[base].agentes[code]
    setConfig(newConfig)
  }

  if (loading) return <div className="card"><p>Carregando configuração...</p></div>

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h3>⚙️ Gerenciador de Bases (Siget)</h3>
        <div>
          <button onClick={handleSave} style={{ background: '#27ae60', padding: '0.5rem 1rem', marginRight: '0.5rem' }}>💾 Salvar Tudo</button>
          <button onClick={fetchConfig} style={{ background: '#555', padding: '0.5rem 1rem' }}>🔄 Recarregar</button>
        </div>
      </div>

      <p style={{ fontSize: '0.9em', color: '#aaa', marginBottom: '1rem' }}>
        Gerencie aqui as Bases, Emails e Agentes (Transmissoras) que o robô deve processar.
      </p>

      {/* Lista de Bases */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {Object.keys(config).map(base => (
          <div key={base} style={{ border: '1px solid #444', borderRadius: '8px', overflow: 'hidden' }}>
            <div
              onClick={() => setExpandedBase(expandedBase === base ? null : base)}
              style={{
                background: '#333',
                padding: '1rem',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
            >
              <span style={{ fontWeight: 'bold', fontSize: '1.1em' }}>{base}</span>
              <span style={{ fontSize: '0.8em', color: '#aaa' }}>
                {config[base]?.email || 'Sem email'} | {Object.keys(config[base]?.agentes || {}).length} agentes
                <span style={{ marginLeft: '1rem' }}>{expandedBase === base ? '▼' : '▶'}</span>
              </span>
            </div>

            {expandedBase === base && (
              <div style={{ padding: '1rem', background: '#222' }}>
                {/* Config da Base */}
                <div style={{ marginBottom: '1rem' }}>
                  <label style={{ display: 'block', fontSize: '0.8em', marginBottom: '0.3rem', color: '#aaa' }}>Email de Acesso (Login):</label>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <input
                      type="text"
                      value={config[base].email || ''}
                      onChange={e => updateEmail(base, e.target.value)}
                      placeholder="ex: tust@empresa.com.br"
                      style={{ flex: 1, padding: '0.5rem', background: '#111', border: '1px solid #555', color: 'white', borderRadius: '4px' }}
                    />
                    <button onClick={(e) => { e.stopPropagation(); removeBase(base); }} style={{ background: '#c0392b', padding: '0 1rem' }}>EXCLUIR BASE</button>
                  </div>
                </div>

                {/* Lista de Agentes */}
                <div style={{ marginTop: '1.5rem' }}>
                  <h4 style={{ borderBottom: '1px solid #444', paddingBottom: '0.5rem', marginBottom: '0.5rem' }}>Agentes / Transmissoras</h4>

                  <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '1rem' }}>
                    <thead>
                      <tr style={{ textAlign: 'left', color: '#aaa', fontSize: '0.9em' }}>
                        <th style={{ padding: '0.5rem' }}>Cód. ONS</th>
                        <th style={{ padding: '0.5rem' }}>Nome Agente</th>
                        <th style={{ padding: '0.5rem', width: '40px' }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(config[base].agentes || {}).map(([code, name]) => (
                        <tr key={code} style={{ borderBottom: '1px solid #333' }}>
                          <td style={{ padding: '0.5rem', fontFamily: 'monospace' }}>{code}</td>
                          <td style={{ padding: '0.5rem' }}>{name}</td>
                          <td style={{ padding: '0.5rem' }}>
                            <button
                              onClick={() => removeAgent(base, code)}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#e74c3c', fontSize: '1.2em' }}
                              title="Remover Agente"
                            >
                              ✖
                            </button>
                          </td>
                        </tr>
                      ))}
                      {Object.keys(config[base].agentes || {}).length === 0 && (
                        <tr><td colSpan="3" style={{ padding: '1rem', textAlign: 'center', color: '#666' }}>Nenhum agente cadastrado.</td></tr>
                      )}
                    </tbody>
                  </table>

                  {/* Adicionar Agente */}
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', background: '#333', padding: '0.5rem', borderRadius: '4px' }}>
                    <input
                      placeholder="Cód. (ex: 4284)"
                      value={newAgentCode}
                      onChange={e => setNewAgentCode(e.target.value)}
                      style={{ width: '120px', padding: '0.4rem', background: '#111', border: '1px solid #555', color: 'white', borderRadius: '4px' }}
                    />
                    <input
                      placeholder="Nome do Agente"
                      value={newAgentName}
                      onChange={e => setNewAgentName(e.target.value)}
                      style={{ flex: 1, padding: '0.4rem', background: '#111', border: '1px solid #555', color: 'white', borderRadius: '4px' }}
                    />
                    <button onClick={() => addAgent(base)} style={{ background: '#2980b9' }}>+ Adicionar</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Adicionar Nova Base */}
      <div style={{ marginTop: '2rem', borderTop: '1px solid #444', paddingTop: '1rem' }}>
        <h4>Adicionar Nova Base</h4>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            placeholder="Nome da Base (ex: SJP, PANTANAL...)"
            value={newBaseName}
            onChange={e => setNewBaseName(e.target.value)}
            style={{ flex: 1, padding: '0.6rem', background: '#333', border: '1px solid #555', color: 'white', borderRadius: '4px' }}
          />
          <button onClick={addBase} style={{ background: '#2980b9', padding: '0 1.5rem' }}>Criar Base</button>
        </div>
      </div>

    </div>
  )
}

export default App
