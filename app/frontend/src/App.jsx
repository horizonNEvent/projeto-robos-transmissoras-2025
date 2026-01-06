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

  // --- Transmissoras Logic ---
  const [showTransmissoras, setShowTransmissoras] = useState(false)
  const [transmissoras, setTransmissoras] = useState([])
  const [importStats, setImportStats] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [transmissoraSearch, setTransmissoraSearch] = useState("")
  const [selectedTransmissoraDetails, setSelectedTransmissoraDetails] = useState(null)

  const fetchTransmissoras = async () => {
    try {
      const res = await axios.get(`${API_URL}/transmissoras`)
      setTransmissoras(res.data)
    } catch (err) {
      console.error("Erro ao buscar transmissoras", err)
    }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    setIsUploading(true)
    setImportStats(null)

    try {
      const res = await axios.post(`${API_URL}/transmissoras/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setImportStats(res.data.stats)
      setLogs(prev => [...prev, `Planilha processada: ${res.data.message}`])
      fetchTransmissoras()
    } catch (err) {
      alert("Erro no upload: " + (err.response?.data?.detail || err.message))
    } finally {
      setIsUploading(false)
      // Limpa input
      e.target.value = ''
    }
  }

  const handleClearTransmissoras = async () => {
    if (!confirm("Tem certeza que deseja apagar TODAS as transmissoras da base? Esta ação não pode ser desfeita.")) return;
    try {
      await axios.delete(`${API_URL}/transmissoras`);
      fetchTransmissoras();
      alert("Base limpa com sucesso!");
    } catch (err) {
      alert("Erro ao limpar base: " + err.message);
    }
  }

  useEffect(() => {
    if (showTransmissoras) fetchTransmissoras()
  }, [showTransmissoras])


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

            <div style={{ marginTop: '1rem', borderTop: '1px solid #333', paddingTop: '1rem' }}>
              <button
                onClick={() => setShowTransmissoras(true)}
                style={{
                  width: '100%',
                  background: '#8e44ad',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem'
                }}
              >
                📊 Cadastro via Planilha
              </button>
            </div>
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
      </div>

      {/* Modal de Seleção de Robô */}
      {showRobotSelector && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          backgroundColor: 'rgba(0,0,0,0.8)',
          zIndex: 9998,
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
              style={{ width: '100%', padding: '0.8rem', marginBottom: '1rem', background: '#333', border: '1px solid #444', borderRadius: '6px', color: 'white' }}
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
                    cursor: 'pointer'
                  }}
                >
                  <span style={{ fontWeight: 'bold' }}>{robot.name}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )
      }

      {/* Modal de Gerenciamento de Transmissoras (Planilha) */}
      {
        showTransmissoras && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(0,0,0,0.85)',
            zIndex: 9999,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            backdropFilter: 'blur(5px)'
          }}>
            <div style={{
              background: '#1a1a1a',
              padding: '2rem',
              borderRadius: '16px',
              width: '95%',
              maxWidth: '900px',
              maxHeight: '90vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              border: '1px solid #444',
              boxShadow: '0 20px 50px rgba(0,0,0,0.6)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <div>
                  <h2 style={{ margin: 0 }}>📊 Base de Transmissoras</h2>
                  <p style={{ margin: 0, color: '#888', fontSize: '0.9em' }}>Sincronização via Planilha Excel (UPSERT)</p>
                </div>
                <div style={{ display: 'flex', gap: '1rem' }}>
                  <input
                    type="text"
                    placeholder="🔍 Buscar Transmissora (CNPJ, Nome, ONS...)"
                    value={transmissoraSearch}
                    onChange={e => setTransmissoraSearch(e.target.value)}
                    style={{
                      padding: '0.6rem 1rem',
                      borderRadius: '8px',
                      border: '1px solid #444',
                      background: '#222',
                      color: 'white',
                      width: '300px'
                    }}
                  />
                  <button onClick={() => setShowTransmissoras(false)} style={{ background: '#333', border: 'none', borderRadius: '50%', width: '40px', height: '40px', fontSize: '1.2em', cursor: 'pointer' }}>×</button>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '1rem', background: '#222', padding: '1.5rem', borderRadius: '12px', marginBottom: '1.5rem', border: '1px solid #333' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem' }}>Upload de Nova Planilha</label>
                  <input
                    type="file"
                    accept=".xls,.xlsx"
                    onChange={handleFileUpload}
                    style={{ display: 'block', width: '100%', background: '#111', padding: '0.5rem', borderRadius: '4px', border: '1px dashed #555' }}
                  />
                  <p style={{ fontSize: '0.75em', color: '#666', marginTop: '0.5rem' }}>Requisito: Coluna "cnpj" presente. Outras colunas serão mapeadas automaticamente.</p>
                </div>
                <button onClick={handleClearTransmissoras} style={{ background: '#c0392b', fontSize: '0.8em', padding: '0.5rem 1rem' }}>🧹 Limpar Banco</button>
                {importStats && (
                  <div style={{ minWidth: '200px', background: '#111', padding: '1rem', borderRadius: '8px', border: '1px solid #27ae60' }}>
                    <h4 style={{ margin: '0 0 0.5rem 0', color: '#27ae60' }}>Resultado Importação</h4>
                    <div style={{ fontSize: '0.85em' }}>
                      <div>✅ Inseridos: {importStats.inserted}</div>
                      <div>🔄 Atualizados: {importStats.updated}</div>
                      <div>⚠️ Erros: {importStats.errors}</div>
                    </div>
                  </div>
                )}
                {isUploading && (
                  <div style={{ display: 'flex', alignItems: 'center', color: 'var(--accent)' }}>
                    ⏳ Processando...
                  </div>
                )}
              </div>

              <div style={{ flex: 1, overflowY: 'auto', background: '#111', borderRadius: '8px', border: '1px solid #333', position: 'relative' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead style={{ position: 'sticky', top: 0, background: '#2a2a2a', zIndex: 1 }}>
                    <tr style={{ textAlign: 'left', fontSize: '0.85em' }}>
                      <th style={{ padding: '1rem' }}>CNPJ</th>
                      <th style={{ padding: '1rem' }}>Nome / Razão Social</th>
                      <th style={{ padding: '1rem' }}>Sigla</th>
                      <th style={{ padding: '1rem' }}>Grupo</th>
                      <th style={{ padding: '1rem' }}>Cód. ONS</th>
                      <th style={{ padding: '1rem' }}>Sinc.</th>
                      <th style={{ padding: '1rem' }}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transmissoras
                      .filter(t => {
                        const search = transmissoraSearch.toLowerCase();
                        return t.cnpj?.toLowerCase().includes(search) ||
                          t.nome?.toLowerCase().includes(search) ||
                          t.sigla?.toLowerCase().includes(search) ||
                          t.codigo_ons?.toLowerCase().includes(search) ||
                          t.grupo?.toLowerCase().includes(search);
                      })
                      .map(t => (
                        <tr key={t.id} style={{ borderBottom: '1px solid #222', fontSize: '0.9em' }}>
                          <td style={{ padding: '0.8rem', color: '#888', fontFamily: 'monospace' }}>{t.cnpj}</td>
                          <td style={{ padding: '0.8rem', fontWeight: 'bold' }}>{t.nome}</td>
                          <td style={{ padding: '0.8rem', color: 'var(--accent)' }}>{t.sigla}</td>
                          <td style={{ padding: '0.8rem' }}>{t.grupo}</td>
                          <td style={{ padding: '0.8rem', color: '#aaa' }}>{t.codigo_ons}</td>
                          <td style={{ padding: '0.8rem', fontSize: '0.75em', color: '#555' }}>{t.ultima_atualizacao}</td>
                          <td style={{ padding: '0.8rem' }}>
                            <button
                              onClick={() => setSelectedTransmissoraDetails(t)}
                              style={{ padding: '4px 8px', fontSize: '0.8em', background: '#444' }}
                            >
                              👁️ Detalhes
                            </button>
                          </td>
                        </tr>
                      ))}
                    {transmissoras.length === 0 && (
                      <tr>
                        <td colSpan="7" style={{ textAlign: 'center', padding: '3rem', color: '#555' }}>Nenhuma transmissora cadastrada. Faça upload de uma planilha para começar.</td>
                      </tr>
                    )}
                  </tbody>
                </table>

                {/* Modal de Detalhes (Estilo Protheus/ONS como no print) */}
                {selectedTransmissoraDetails && (
                  <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    backgroundColor: 'rgba(0,0,0,0.9)',
                    zIndex: 10000,
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    padding: '2rem'
                  }}>
                    <div style={{
                      background: '#fff',
                      color: '#333',
                      width: '100%',
                      maxWidth: '1000px',
                      maxHeight: '95vh',
                      borderRadius: '4px',
                      overflow: 'hidden',
                      display: 'flex',
                      flexDirection: 'column',
                      boxShadow: '0 20px 60px rgba(0,0,0,0.8)',
                      fontFamily: 'Segoe UI, Helvetica, sans-serif'
                    }}>
                      {/* Header Cinza */}
                      <div style={{ background: '#f5f5f5', padding: '10px 20px', borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontWeight: 'bold', fontSize: '13px' }}>Código</span>
                            <div style={{ border: '1px solid #88ba2a', padding: '2px 10px', fontWeight: 'bold' }}>{selectedTransmissoraDetails.codigo_ons}</div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontWeight: 'bold', fontSize: '13px' }}>Sigla</span>
                            <div style={{ border: '1px solid #88ba2a', padding: '2px 10px', color: '#333', fontWeight: 'bold' }}>{selectedTransmissoraDetails.sigla}</div>
                          </div>
                        </div>
                        <button onClick={() => setSelectedTransmissoraDetails(null)} style={{ background: '#e74c3c', border: 'none', color: 'white', padding: '5px 15px', cursor: 'pointer', borderRadius: '4px' }}>FECHAR</button>
                      </div>

                      {/* Conteúdo Scrollável */}
                      <div style={{ padding: '20px', overflowY: 'auto', backgroundColor: '#fff' }}>
                        {(() => {
                          const d = JSON.parse(selectedTransmissoraDetails.dados_json || "{}");
                          const rowStyle = { display: 'flex', gap: '1rem', marginBottom: '8px', fontSize: '12px' };
                          const labelStyle = { color: '#000', fontWeight: 'bold', minWidth: '100px' };
                          const sectionTitleStyle = { color: '#88ba2a', fontSize: '14px', fontWeight: 'bold', borderBottom: '1px solid #88ba2a', paddingBottom: '2px', marginBottom: '10px', marginTop: '15px' };
                          const boxStyle = { border: '1px solid #ccc', padding: '10px', borderRadius: '2px', marginBottom: '10px' };

                          return (
                            <>
                              <div style={sectionTitleStyle}>VINCULAÇÃO AO SACT</div>
                              <div style={boxStyle}>
                                <div style={rowStyle}>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Agente SACT:</span> {d.agente_sact || d.sigla_do_agente}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Concessão:</span> {d.concessao}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Data:</span> {d.dt_concessao}</div>
                                </div>
                                <div style={rowStyle}>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Contrato:</span> {d.contrato}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Termo Aditivo Vigente:</span> {d.termo_aditivo_vigente || '-'}</div>
                                </div>
                              </div>

                              <div style={sectionTitleStyle}>DADOS GERAIS</div>
                              <div style={boxStyle}>
                                <div style={rowStyle}>
                                  <div style={{ flex: 2 }}><span style={labelStyle}>Responsável:</span> {d.nome_do_representante}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Status:</span> <span style={{ color: 'green', fontWeight: 'bold' }}>Ativo</span></div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Classificação:</span> {d.classificacao_empresa}</div>
                                </div>
                                <div style={rowStyle}>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Início Contábil:</span> {d.dt_inicio_contabil}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Operação:</span> {d.dt_inicio_operacao}</div>
                                </div>
                              </div>

                              <div style={sectionTitleStyle}>DADOS DO AGENTE</div>
                              <div style={boxStyle}>
                                <div style={rowStyle}>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Razão Social:</span> {d.razao_social}</div>
                                </div>
                                <div style={rowStyle}>
                                  <div style={{ flex: 2 }}><span style={labelStyle}>CNPJ:</span> {selectedTransmissoraDetails.cnpj}</div>
                                  <div style={{ flex: 1.5 }}><span style={labelStyle}>Inscrição Estadual:</span> {d.inscricao_estadual}</div>
                                  <div style={{ flex: 1 }}><input type="checkbox" readOnly /> Padrão Desligamento</div>
                                </div>
                                <div style={rowStyle}>
                                  <div style={{ flex: 2 }}><span style={labelStyle}>Logradouro:</span> {d.logradouro}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Número:</span> {d.numero}</div>
                                </div>
                                <div style={rowStyle}>
                                  <div style={{ flex: 2 }}><span style={labelStyle}>Complemento:</span> {d.complemento}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Bairro:</span> {d.bairro}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>CEP:</span> {d.cep}</div>
                                </div>
                                <div style={rowStyle}>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Estado:</span> {d.uf}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Cidade:</span> {d.cidade}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Região:</span> {d.regiao}</div>
                                </div>
                              </div>

                              <div style={sectionTitleStyle}>DADOS BANCÁRIOS</div>
                              <div style={boxStyle}>
                                <div style={rowStyle}>
                                  <div style={{ flex: 2 }}><span style={labelStyle}>Banco:</span> {d.banco}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Número:</span> {d.numero_do_banco}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Agência:</span> {d.agencia}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Conta:</span> {d.conta}</div>
                                </div>
                              </div>

                              <div style={sectionTitleStyle}>DADOS FISCAIS</div>
                              <div style={boxStyle}>
                                <div style={rowStyle}>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>PIS/COFINS %:</span> {d.aliquota_pis_confins || '0,00'}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Alíquota RGR %:</span> {d.aliquota_rgr || '0,00'}</div>
                                  <div style={{ flex: 1 }}><input type="checkbox" readOnly /> Incluir PIS/COFINS</div>
                                </div>
                                <div style={rowStyle}>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>RAP RB %:</span> {d.participacao_rap_rb || '-'}</div>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>RAP RF %:</span> {d.participacao_rap_rf || '-'}</div>
                                </div>
                              </div>

                              <div style={sectionTitleStyle}>ENCAMINHAMENTO DAS FATURAS</div>
                              <div style={boxStyle}>
                                <div style={rowStyle}>
                                  <div style={{ flex: 1 }}><span style={labelStyle}>Forma:</span> {d.forma_de_encaminhamento_das_fat}</div>
                                  <div style={{ flex: 2 }}><span style={labelStyle}>URL do Site:</span> <a href={d.url_do_site} target="_blank" rel="noreferrer" style={{ color: '#2980b9' }}>{d.url_do_site}</a></div>
                                </div>
                              </div>

                              <div style={sectionTitleStyle}>REPRESENTANTES</div>
                              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', border: '1px solid #ccc' }}>
                                <thead style={{ background: '#88ba2a', color: '#fff' }}>
                                  <tr style={{ textAlign: 'left' }}>
                                    <th style={{ padding: '5px' }}>Nome</th>
                                    <th style={{ padding: '5px' }}>Telefone</th>
                                    <th style={{ padding: '5px' }}>E-mail</th>
                                    <th style={{ padding: '5px' }}>Funções</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {(d.representantes_list && d.representantes_list.length > 0
                                    ? d.representantes_list
                                    : [{
                                      nome: d.nome_do_representante,
                                      telefone: d.telefone,
                                      email: d.email,
                                      funcao: d.funcao_do_representante
                                    }]
                                  ).map((r, idx) => (
                                    <tr key={idx} style={{ borderBottom: '1px solid #eee' }}>
                                      <td style={{ padding: '5px' }}>{r.nome}</td>
                                      <td style={{ padding: '5px' }}>{r.telefone}</td>
                                      <td style={{ padding: '5px' }}>{r.email}</td>
                                      <td style={{ padding: '5px' }}>{r.funcao}</td>
                                    </tr>
                                  ))}
                                  {((!d.representantes_list || d.representantes_list.length === 0) && !d.nome_do_representante && !d.email) && (
                                    <tr><td colSpan="4" style={{ padding: '10px', textAlign: 'center', color: '#888' }}>Nenhum representante cadastrado.</td></tr>
                                  )}
                                </tbody>
                              </table>
                            </>
                          )
                        })()}
                      </div>
                    </div>
                  </div>
                )}
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
            // Assume que o item é {key: value }
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
