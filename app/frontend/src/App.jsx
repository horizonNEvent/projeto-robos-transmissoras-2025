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
  const [robotSearch, setRobotSearch] = useState('')

  // Definição dos Robôs
  const ROBOTS = [
    { id: 'siget', name: 'WebSiget', icon: '🤖' },
    { id: 'cnt', name: 'WebCnt', icon: '⚡' },
    { id: 'pantanal', name: 'WebPantanal', icon: '🐊' },
    { id: 'assu', name: 'WebAssu', icon: '🌪️' },
    { id: 'tropicalia', name: 'WebTropicalia', icon: '🌴' },
    // Futuros robôs podem ser adicionados aqui
  ]
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
        payload.base = sigetBase
        payload.email = sigetEmail
        setLogs(prev => [...prev, `Configuração Siget: Base=${sigetBase}, Email=${sigetEmail}`])
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





            <div style={{ marginBottom: '1rem' }}>
              <input
                type="text"
                placeholder="🔍 Buscar Robô..."
                value={robotSearch}
                onChange={e => setRobotSearch(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.6rem',
                  marginBottom: '0.8rem',
                  background: '#333',
                  border: '1px solid #444',
                  borderRadius: '6px',
                  color: 'white'
                }}
              />

              <div style={{
                display: 'flex',
                gap: '0.8rem',
                overflowX: 'auto',
                paddingBottom: '0.5rem',
                scrollbarWidth: 'thin',
                scrollbarColor: 'var(--accent) #222'
              }}>
                {filteredRobots.map(robot => (
                  <button
                    key={robot.id}
                    onClick={() => setSelectedRobot(robot.id)}
                    style={{
                      minWidth: '100px',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '0.3rem',
                      padding: '0.8rem',
                      backgroundColor: selectedRobot === robot.id ? 'var(--accent)' : '#2a2a2a',
                      border: selectedRobot === robot.id ? '1px solid var(--accent)' : '1px solid #444',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      opacity: selectedRobot === robot.id ? 1 : 0.7,
                      transition: 'all 0.2s'
                    }}
                  >
                    <span style={{ fontSize: '1.5em' }}>{robot.icon}</span>
                    <span style={{ fontSize: '0.85em', fontWeight: 'bold' }}>{robot.name}</span>
                  </button>
                ))}
                {filteredRobots.length === 0 && <p style={{ color: '#888', fontSize: '0.8em', width: '100%', textAlign: 'center' }}>Nenhum robô encontrado.</p>}
              </div>
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

          <div className="card" style={{ textAlign: 'left', maxHeight: '300px', overflowY: 'auto' }}>
            <h3>Logs de Atividade</h3>
            <ul style={{ listStyle: 'none', padding: 0, fontSize: '0.9em', color: '#aaa' }}>
              {logs.map((log, i) => <li key={i}>{log}</li>)}
            </ul>
          </div>
        </div>

        <div className="data-panel">
          {selectedRobot === 'siget' ? (
            <div className="card">
              <h3>⚙️ Configuração WebSiget</h3>
              <p style={{ fontSize: '0.9em', color: '#aaa', marginBottom: '1rem' }}>
                Especifique a Base e o E-mail de login para executar o robô.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '0.3rem' }}>Base Selecionada</label>
                  <select
                    value={sigetBase}
                    onChange={(e) => setSigetBase(e.target.value)}
                    style={{ padding: '0.5em', width: '100%', borderRadius: '4px', border: '1px solid #444', background: '#222', color: 'white' }}
                  >
                    {/* Opções dinâmicas baseadas no banco */}
                    {[...new Set(empresas.map(e => e.base))].sort().map(base => (
                      <option key={base} value={base}>{base}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '0.3rem' }}>E-mail Credencial</label>
                  <input
                    type="email"
                    value={sigetEmail}
                    onChange={(e) => setSigetEmail(e.target.value)}
                    style={{ padding: '0.5em', width: '100%', borderRadius: '4px', border: '1px solid #444', background: '#222', color: 'white' }}
                  />
                  <button
                    onClick={handleSaveSigetCreds}
                    style={{ marginTop: '0.5rem', fontSize: '0.8em', padding: '0.4em 0.8em', background: '#444', border: 'none', cursor: 'pointer', borderRadius: '4px' }}
                  >
                    💾 Salvar para {sigetBase}
                  </button>
                </div>

                <div style={{ marginTop: '1rem', padding: '1rem', background: '#2a2a2a', borderRadius: '4px' }}>
                  <h4>Empresas na Base: {sigetBase}</h4>
                  <ul style={{ fontSize: '0.85em', color: '#ccc', paddingLeft: '1.2rem', marginTop: '0.5rem' }}>
                    {empresas.filter(e => e.base === sigetBase).length > 0 ? (
                      empresas.filter(e => e.base === sigetBase).map(e => <li key={e.id}>{e.nome_empresa} ({e.codigo_ons})</li>)
                    ) : (
                      <li>Nenhuma empresa cadastrada nesta base.</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
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

      </div>
    </>
  )
}

export default App
