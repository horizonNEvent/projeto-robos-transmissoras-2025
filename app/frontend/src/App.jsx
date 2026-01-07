import { useState, useEffect } from 'react'
import axios from 'axios'
import './index.css'

// Constants
import { ROBOTS } from './constants/robots'

// Components
import RobotConfigManager from './components/RobotConfigManager'
import TransmissoraModal from './components/TransmissoraModal'
import EmpresaManager from './components/EmpresaManager'
import SigetPublicManager from './components/SigetPublicManager'
import LogsPanel from './components/LogsPanel'

const API_URL = "/api"

function App() {
  const [activeTab, setActiveTab] = useState('dashboard') // dashboard, robot_id, transmissoras, config
  const [status, setStatus] = useState('idle')
  const [logs, setLogs] = useState([])
  const [downloadUrl, setDownloadUrl] = useState(null)
  const [empresas, setEmpresas] = useState([])
  const [selectedRobotId, setSelectedRobotId] = useState('siget')
  const [robotSearch, setRobotSearch] = useState('')
  const [empresasMapping, setEmpresasMapping] = useState({})
  const [selectedEmpresaFilter, setSelectedEmpresaFilter] = useState('')
  const [selectedAgenteFilter, setSelectedAgenteFilter] = useState('')
  const [selectedProcessIds, setSelectedProcessIds] = useState([])
  const [activePids, setActivePids] = useState([])
  const [robotConfigs, setRobotConfigs] = useState([])
  const [transmissoras, setTransmissoras] = useState([])
  const [showTransmissorasModal, setShowTransmissorasModal] = useState(false)
  const [showSigetPublicModal, setShowSigetPublicModal] = useState(false)

  // Filtros de Consulta Transmissoras
  const [tFilterCNPJ, setTFilterCNPJ] = useState('')
  const [tFilterNome, setTFilterNome] = useState('')
  const [tFilterSigla, setTFilterSigla] = useState('')
  const [tFilterONS, setTFilterONS] = useState('')

  // Form states for EmpresaManager
  const [formData, setFormData] = useState({ codigo_ons: '', nome_empresa: '', base: 'AETE' })
  const [editingId, setEditingId] = useState(null)

  useEffect(() => {
    fetchEmpresas()
    fetchMapping()
    fetchRobotConfigs()
    fetchTransmissoras()
  }, [])

  const addLog = (msg) => {
    setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 100))
  }

  const fetchEmpresas = async () => {
    try {
      const res = await axios.get(`${API_URL}/empresas`)
      setEmpresas(res.data)
    } catch (err) { console.error(err) }
  }

  const fetchMapping = async () => {
    try {
      const res = await axios.get(`${API_URL}/empresas/mapping`)
      setEmpresasMapping(res.data)
    } catch (err) { console.error(err) }
  }

  const fetchRobotConfigs = async () => {
    try {
      const res = await axios.get(`${API_URL}/config/robots`)
      setRobotConfigs(res.data || [])
    } catch (err) { console.error(err) }
  }

  const fetchTransmissoras = async () => {
    try {
      const res = await axios.get(`${API_URL}/transmissoras`)
      setTransmissoras(res.data)
    } catch (err) { console.error(err) }
  }

  const handleRunRobot = async () => {
    if (status === 'running') return;
    if (selectedProcessIds.length === 0) {
      alert("Por favor, selecione ao menos um Processo de Execução (Perfil) antes de iniciar.");
      return;
    }

    setStatus('running');
    setDownloadUrl(null);
    addLog(`Solicitando início assíncrono de ${selectedProcessIds.length} processos...`);

    try {
      const selectedProcesses = robotConfigs.filter(c => selectedProcessIds.includes(c.id));

      const requests = selectedProcesses.map(process => {
        const payload = {
          robot_name: selectedRobotId,
          empresa: process.base || process.label,
          agente: selectedAgenteFilter || null,
          user: process.username || null,
          password: process.password || null,
          competencia: ((selectedRobotId === 'websigetpublic' || selectedRobotId === 'webtaesa') && window.tempCompetencia) ? window.tempCompetencia : null,
          process_id: process.id
        }
        addLog(`Gatilho disparado para: ${process.label} (${process.base})`);
        return axios.post(`${API_URL}/run-robot`, payload);
      });

      await Promise.all(requests);
      addLog(`Todos os ${selectedProcessIds.length} robôs foram colocados em fila de execução.`);
      pollStatus(selectedRobotId);
    } catch (err) {
      setStatus('idle');
      addLog(`Erro ao iniciar processos: ${err.message}`);
    }
  }

  const pollStatus = async (robotId) => {
    try {
      const res = await axios.get(`${API_URL}/robot-status/${robotId}`);
      const s = res.data.status;
      const pids = res.data.active_pids || [];

      setActivePids(pids);

      if (s === 'running' || pids.length > 0) {
        setStatus('running');
        setTimeout(() => pollStatus(robotId), 5000);
      } else {
        // Se status não é running e não há pids ativos, assumimos que terminou
        setStatus('finished');
        addLog(`Todos os processos do ${robotId.toUpperCase()} foram concluídos.`);
        setDownloadUrl(`${API_URL}/download-results?robot=${robotId}`);
        setSelectedProcessIds([]); // Limpa seleção ao terminar
      }
    } catch (e) {
      setTimeout(() => pollStatus(robotId), 5000);
    }
  }

  const downloadResults = () => {
    const url = downloadUrl || `${API_URL}/download-results?robot=${selectedRobotId}`
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const currentRobot = ROBOTS.find(r => r.id === selectedRobotId)

  return (
    <div className="app-container">
      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>ROBO RUNNER</h1>
        </div>

        <div className="sidebar-search">
          <input
            placeholder="🔍 Buscar robô..."
            value={robotSearch}
            onChange={e => setRobotSearch(e.target.value)}
          />
        </div>

        <div className="sidebar-nav">
          <div
            className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            🏠 Dashboard
          </div>

          <div style={{ padding: '1rem 1rem 0.5rem', fontSize: '0.65rem', color: '#475569', fontWeight: 'bold', textTransform: 'uppercase' }}>
            Automações
          </div>

          {ROBOTS.filter(r => r.name.toLowerCase().includes(robotSearch.toLowerCase())).map(r => (
            <div
              key={r.id}
              className={`nav-item ${activeTab === 'robot' && selectedRobotId === r.id ? 'active' : ''}`}
              onClick={() => {
                setSelectedRobotId(r.id)
                setActiveTab('robot')
              }}
            >
              🤖 {r.name}
              {r.type === 'ie' && <span className="nav-item-type">IE</span>}
            </div>
          ))}

          <div style={{ padding: '1.5rem 1rem 0.5rem', fontSize: '0.65rem', color: '#475569', fontWeight: 'bold', textTransform: 'uppercase' }}>
            Base de Dados
          </div>

          <div
            className={`nav-item ${activeTab === 'transmissoras' ? 'active' : ''}`}
            onClick={() => setActiveTab('transmissoras')}
          >
            📊 Transmissoras
          </div>

          <div
            className={`nav-item ${activeTab === 'config' ? 'active' : ''}`}
            onClick={() => setActiveTab('config')}
          >
            ⚙️ Credenciais Central
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT */}
      <main className="main-content">
        {activeTab === 'dashboard' && (
          <div className="dashboard-view">
            <header className="content-header">
              <h2>Visão Geral</h2>
            </header>
            <div className="dashboard-grid">
              <div className="card">
                <h3>Robôs Disponíveis</h3>
                <p style={{ fontSize: '2rem', fontWeight: 'bold', margin: 0 }}>{ROBOTS.length}</p>
              </div>
              <div className="card">
                <h3>Credenciais Ativas</h3>
                <p style={{ fontSize: '2rem', fontWeight: 'bold', margin: 0 }}>{robotConfigs.length}</p>
              </div>
              <div className="card">
                <h3>Transmissoras Base</h3>
                <p style={{ fontSize: '2rem', fontWeight: 'bold', margin: 0 }}>{transmissoras.length}</p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'robot' && currentRobot && (
          <div className="robot-view">
            <header className="content-header">
              <div className="robot-title">
                <h2>{currentRobot.name}</h2>
                <div className={`status-badge status-${status}`}>
                  {status === 'idle' ? 'Disponível' : status === 'running' ? 'Em Execução' : 'Finalizado'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '1rem' }}>
                {(downloadUrl || status === 'finished') && (
                  <button onClick={downloadResults} style={{ background: '#10b981' }}>
                    ⬇️ Baixar
                  </button>
                )}
                {selectedRobotId === 'websigetpublic' && (
                  <button onClick={() => setShowSigetPublicModal(true)} style={{ background: '#8b5cf6' }}>
                    🎯 Parametrizar Alvos
                  </button>
                )}
                <button onClick={handleRunRobot} disabled={status === 'running'}>
                  {status === 'running' ? '🚀 Rodando...' : '▶ Iniciar Execução'}
                </button>
              </div>
            </header>

            {/* Input Extra para SigetPublic: Competência */}
            {(selectedRobotId === 'websigetpublic' || selectedRobotId === 'webtaesa') && (
              <div style={{ margin: '1rem', padding: '1rem', background: '#334155', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <label style={{ color: '#cbd5e1', fontWeight: 'bold' }}>📅 Competência (YYYYMM):</label>
                <input
                  type="text"
                  placeholder="Ex: 202602 (Deixe vazio para Auto)"
                  style={{ background: '#1e293b', border: '1px solid #475569', color: 'white', padding: '0.5rem', borderRadius: '4px' }}
                  onChange={(e) => {
                    // Gambiarra: Salvamos no filtro de empresa temporariamente ou criamos state novo?
                    // Melhor criar um state local rápido se não quisermos mexer muito
                    window.tempCompetencia = e.target.value;
                  }}
                />
                <small style={{ color: '#94a3b8' }}>Se vazio, usa mês seguinte atual.</small>
              </div>
            )}

            <div className="dashboard-grid">
              {/* Seleção de Processo / Perfil */}
              <div className="card control-card" style={{ gridColumn: '1 / -1' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3>Selecione o Processo de Execução</h3>
                  <button
                    onClick={() => {
                      // Abre modal ou scrolla para o manager
                      setSelectedProcessId(null)
                      const el = document.getElementById('config-manager-section')
                      if (el) el.scrollIntoView({ behavior: 'smooth' })
                    }}
                    style={{ background: 'transparent', border: '1px solid var(--accent)', color: 'var(--accent)', padding: '0.4rem 1rem', fontSize: '0.8rem' }}
                  >
                    + Novo Processo
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
                  {robotConfigs
                    .filter(c => c.robot_type.toUpperCase() === (currentRobot.type === 'ie' ? 'WEBIE' : currentRobot.id.toUpperCase()))
                    .map(process => {
                      const isSelected = selectedProcessIds.includes(process.id);
                      const isActive = activePids.includes(process.id);
                      return (
                        <div
                          key={process.id}
                          onClick={() => {
                            if (isActive) return; // Não permite desativar enquanto roda
                            setSelectedProcessIds(prev =>
                              prev.includes(process.id)
                                ? prev.filter(id => id !== process.id)
                                : [...prev, process.id]
                            )
                          }}
                          style={{
                            padding: '1rem',
                            background: isActive
                              ? 'rgba(56, 189, 248, 0.1)'
                              : isSelected ? 'linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(37, 99, 235, 0.2) 100%)' : 'rgba(255,255,255,0.03)',
                            border: `2px solid ${isActive ? '#f59e0b' : isSelected ? 'var(--accent)' : 'rgba(255,255,255,0.05)'}`,
                            borderRadius: '12px',
                            cursor: isActive ? 'not-allowed' : 'pointer',
                            transition: 'all 0.2s',
                            position: 'relative',
                            transform: isSelected ? 'scale(1.02)' : 'scale(1)',
                            opacity: isActive ? 0.8 : 1
                          }}
                        >
                          {isSelected && !isActive && <div style={{ position: 'absolute', top: '-8px', right: '-8px', background: 'var(--accent)', borderRadius: '50%', width: '20px', height: '20px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '12px', fontWeight: 'bold' }}>✓</div>}
                          {isActive && (
                            <div style={{ position: 'absolute', top: '8px', right: '8px', display: 'flex', gap: '4px' }}>
                              <span className="badge" style={{ background: '#f59e0b', fontSize: '0.6rem', padding: '2px 6px' }}>PROCESSANDO</span>
                            </div>
                          )}
                          <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>{process.label}</div>
                          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{process.base} • {Object.keys(JSON.parse(process.agents_json || '{}')).length} agentes</div>
                        </div>
                      )
                    })}
                  {robotConfigs.filter(c => c.robot_type.toUpperCase() === (currentRobot.type === 'ie' ? 'WEBIE' : currentRobot.id.toUpperCase())).length === 0 && (
                    <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '2rem', color: '#475569', border: '1px dashed #334155', borderRadius: '12px' }}>
                      Nenhum processo parametrizado para este robô.
                    </div>
                  )}
                </div>
              </div>

              {/* Painel de Logs em destaque quando rodando */}
              <div className="card" style={{ gridColumn: '1 / -1' }}>
                <h3>Monitoramento de Atividade</h3>
                <LogsPanel logs={logs} />
              </div>

              {/* Gerenciador de Processos (Parametrização) */}
              <div id="config-manager-section" style={{ gridColumn: '1 / -1', marginTop: '1rem' }}>
                <RobotConfigManager
                  transmissoras={transmissoras}
                  empresasMapping={empresasMapping}
                  configs={robotConfigs}
                  onUpdate={fetchRobotConfigs}
                  forcedRobotType={currentRobot.type === 'ie' ? 'WEBIE' : currentRobot.id.toUpperCase()}
                />
              </div>
            </div>
          </div>
        )
        }

        {
          activeTab === 'transmissoras' && (
            <div className="transmissoras-view">
              <header className="content-header" style={{ marginBottom: '1rem' }}>
                <h2>Base de Transmissoras</h2>
                <button onClick={() => setShowTransmissorasModal(true)} style={{ background: '#8b5cf6' }}>
                  📊 Gerenciar Planilha
                </button>
              </header>

              {/* Barra de Filtros */}
              <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
                <div>
                  <label style={{ fontSize: '0.7rem', color: '#64748b', display: 'block', marginBottom: '4px' }}>CNPJ</label>
                  <input
                    placeholder="00.000..."
                    value={tFilterCNPJ}
                    onChange={e => setTFilterCNPJ(e.target.value)}
                    style={{ width: '100%', fontSize: '0.85rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.7rem', color: '#64748b', display: 'block', marginBottom: '4px' }}>NOME</label>
                  <input
                    placeholder="Buscar por nome..."
                    value={tFilterNome}
                    onChange={e => setTFilterNome(e.target.value)}
                    style={{ width: '100%', fontSize: '0.85rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.7rem', color: '#64748b', display: 'block', marginBottom: '4px' }}>SIGLA</label>
                  <input
                    placeholder="Ex: SJP"
                    value={tFilterSigla}
                    onChange={e => setTFilterSigla(e.target.value)}
                    style={{ width: '100%', fontSize: '0.85rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.7rem', color: '#64748b', display: 'block', marginBottom: '4px' }}>CÓDIGO ONS</label>
                  <input
                    placeholder="Ex: 4284"
                    value={tFilterONS}
                    onChange={e => setTFilterONS(e.target.value)}
                    style={{ width: '100%', fontSize: '0.85rem' }}
                  />
                </div>
              </div>
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <table style={{ width: '100%' }}>
                  <thead>
                    <tr>
                      <th>CNPJ</th>
                      <th>Nome</th>
                      <th>Sigla</th>
                      <th>Cód ONS</th>
                      <th>Grupo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transmissoras
                      .filter(t => {
                        const matchCNPJ = !tFilterCNPJ || t.cnpj?.toLowerCase().includes(tFilterCNPJ.toLowerCase());
                        const matchNome = !tFilterNome || t.nome?.toLowerCase().includes(tFilterNome.toLowerCase());
                        const matchSigla = !tFilterSigla || t.sigla?.toLowerCase().includes(tFilterSigla.toLowerCase());
                        const matchONS = !tFilterONS || t.codigo_ons?.toLowerCase().includes(tFilterONS.toLowerCase());
                        return matchCNPJ && matchNome && matchSigla && matchONS;
                      })
                      .slice(0, 100).map(t => (
                        <tr key={t.id}>
                          <td>{t.cnpj}</td>
                          <td style={{ fontWeight: 'bold' }}>{t.nome}</td>
                          <td style={{ color: 'var(--accent)' }}>{t.sigla}</td>
                          <td>{t.codigo_ons}</td>
                          <td>{t.grupo}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
                {transmissoras.length > 50 && (
                  <p style={{ padding: '1rem', textAlign: 'center', color: '#64748b', fontSize: '0.8rem' }}>
                    Exibindo as primeiras 50 de {transmissoras.length} transmissoras.
                  </p>
                )}
              </div>
            </div>
          )
        }

        {
          activeTab === 'config' && (
            <div className="config-view">
              <header className="content-header">
                <h2>Configurações Globais</h2>
              </header>
              <div className="dashboard-grid">
                <div style={{ gridColumn: '1 / -1' }}>
                  <RobotConfigManager
                    transmissoras={transmissoras}
                    empresasMapping={empresasMapping}
                    configs={robotConfigs}
                    onUpdate={fetchRobotConfigs}
                  />
                </div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <EmpresaManager
                    empresas={empresas}
                    onUpdate={fetchEmpresas}
                    onLog={addLog}
                    formData={formData}
                    setFormData={setFormData}
                    editingId={editingId}
                    setEditingId={setEditingId}
                  />
                </div>
              </div>
            </div>
          )
        }
      </main >

      {/* MODALS QUE FICAM POR CIMA */}
      < TransmissoraModal
        show={showTransmissorasModal}
        onClose={() => {
          setShowTransmissorasModal(false)
          fetchTransmissoras()
        }}
        onLog={addLog}
      />

      {/* MODAL CONFIG SIGET PUBLIC */}
      {showSigetPublicModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
          background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
        }}>
          <div className="card" style={{ width: '90%', maxWidth: '900px', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            <button
              onClick={() => setShowSigetPublicModal(false)}
              style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'transparent', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: 'white' }}
            >
              &times;
            </button>
            <div style={{ marginTop: '1rem' }}>
              <SigetPublicManager onLog={addLog} />
            </div>
          </div>
        </div>
      )}
    </div >
  )
}

export default App
