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
import DocumentManager from './components/DocumentManager'
import LogsPanel from './components/LogsPanel'
import ScheduleModal from './components/ScheduleModal'
import ParallelProcessManager from './components/ParallelProcessManager'
import GruposTransmissorasManager from './components/GruposTransmissorasManager'

const API_URL = "/api"

function App() {
  const [activeTab, setActiveTab] = useState('dashboard') // dashboard, robot_id, transmissoras, config, documents
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
  const [formData, setFormData] = useState({ codigo_ons: '', nome_empresa: '', cnpj: '', base: 'AETE' })
  const [editingId, setEditingId] = useState(null)

  // Scheduling states
  const [showScheduleModal, setShowScheduleModal] = useState(false)
  const [scheduledConfigId, setScheduledConfigId] = useState(null)
  const [scheduledConfigLabel, setScheduledConfigLabel] = useState('')
  const [viewingTransmissora, setViewingTransmissora] = useState(null)

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
          competencia: ((['websigetpublic', 'webtaesa', 'light', 'glorian', 'cpfl', 'rialmas', 'rialmav', 'rialmaiv', 'aete', 'transnorte', 'equatorial', 'copel', 'mge', 'stategrid', 'stn', 'tecp', 'elte', 'etes', 'tme', 'etem', 'etvg', 'tne', 'etc', 'etap', 'tcc', 'tpe', 'tsm', 'etb', 'amazonia', 'tcpe', 'vsb', 'verene', 'ons', 'harpix', 'lnt', 'sigetplusv2'].includes(selectedRobotId)) && window.tempCompetencia) ? window.tempCompetencia : null,
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
        setFormData({ codigo_ons: '', nome_empresa: '', cnpj: '', base: 'AETE' })
        setSelectedProcessIds([]); // Limpa seleção ao terminar
      }
    } catch (e) {
      setTimeout(() => pollStatus(robotId), 5000);
    }
  }

  // AMSE Update State
  const [showAmseModal, setShowAmseModal] = useState(false)
  const [amseCreds, setAmseCreds] = useState({ user: '', password: '' })
  const [isAmseRunning, setIsAmseRunning] = useState(false)

  const handleUpdateAmse = async (e) => {
    e.preventDefault()
    if (!amseCreds.user || !amseCreds.password) return alert("Preencha usuário e senha")

    setIsAmseRunning(true)
    addLog("Iniciando atualização via AMSE... Isso pode demorar.")

    try {
      const res = await axios.post(`${API_URL}/transmissoras/update-amse`, amseCreds)

      // Parse logs for specific counts
      const logs = res.data.logs || ""
      const match = logs.match(/New: (\d+), Updated: (\d+)/)

      let msg = "Processo finalizado."
      if (match) {
        msg = `Concluído! ${match[1]} novas transmissoras, ${match[2]} atualizadas.`
      }

      addLog(msg)
      alert(msg)

      console.log(logs)
      setShowAmseModal(false)
      fetchTransmissoras()
    } catch (err) {
      const errorMsg = `Erro AMSE: ${err.response?.data?.detail || err.message}`
      addLog(errorMsg)
      alert(errorMsg)
    } finally {
      setIsAmseRunning(false)
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

          <div
            className={`nav-item ${activeTab === 'processes' ? 'active' : ''}`}
            onClick={() => setActiveTab('processes')}
          >
            🚀 Gerenciador de Processos
          </div>

          <div
            className={`nav-item ${activeTab === 'documents' ? 'active' : ''}`}
            onClick={() => setActiveTab('documents')}
          >
            📦 Documentos Validados
          </div>
          <div
            className={`nav-item ${activeTab === 'grupos' ? 'active' : ''}`}
            onClick={() => setActiveTab('grupos')}
          >
            🏢 Grupos de Transmissoras
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

            {/* Input Extra para SigetPublic / Taesa / Light e novos robôs: Competência */}
            {['websigetpublic', 'webtaesa', 'light', 'glorian', 'cpfl', 'rialmas', 'rialmav', 'rialmaiv', 'aete', 'transnorte', 'equatorial', 'copel', 'mge', 'stategrid', 'stn', 'tecp', 'elte', 'etes', 'tme', 'etem', 'etvg', 'tne', 'etc', 'etap', 'tcc', 'tpe', 'tsm', 'etb', 'amazonia', 'tcpe', 'vsb', 'verene', 'ons', 'harpix', 'lnt', 'sigetplusv2'].includes(selectedRobotId) && (
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
                          <div style={{ fontWeight: 'bold', marginBottom: '4px', display: 'flex', justifyContent: 'space-between' }}>
                            {process.label}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setScheduledConfigId(process.id);
                                setScheduledConfigLabel(process.label);
                                setShowScheduleModal(true);
                              }}
                              style={{
                                background: 'transparent', border: 'none', padding: 0, fontSize: '1rem', cursor: 'pointer',
                                opacity: 0.6
                              }}
                              title="Configurar Agendamento"
                            >
                              🕒
                            </button>
                          </div>
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
                <button onClick={() => setShowTransmissorasModal(true)} style={{ background: '#8b5cf6', marginRight: '1rem' }}>
                  📊 Gerenciar Planilha
                </button>
                <button onClick={() => setShowAmseModal(true)} style={{ background: '#2563eb' }}>
                  🤖 Atualizar via AMSE
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
                      <th>Ações</th>
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
                          <td>
                            <button
                              onClick={() => setViewingTransmissora(t)}
                              title="Ver Detalhes"
                              style={{ background: 'transparent', border: 'none', fontSize: '1.2rem', cursor: 'pointer' }}
                            >
                              👁️
                            </button>
                          </td>
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

          )}

        {
          activeTab === 'processes' && (
            <div className="processes-view">
              <ParallelProcessManager apiBaseUrl={API_URL} />
            </div>
          )
        }

        {activeTab === 'documents' && (
          <div className="documents-view">
            <header className="content-header">
              <h2>Repositório de Documentos</h2>
            </header>
            <DocumentManager />
          </div>
        )}

        {activeTab === 'grupos' && (
          <div style={{ padding: '1.5rem' }}>
            <GruposTransmissorasManager onLog={addLog} />
          </div>
        )}
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

      {/* AMSE MODAL */}
      {showAmseModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
          background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
        }}>
          <div className="card" style={{ width: '400px', position: 'relative' }}>
            <h3>Atualizar via AMSE (ONS)</h3>
            <p style={{ fontSize: '0.8rem', color: '#ccc' }}>Isso irá baixar a planilha mais recente do portal AMSE e atualizar o banco de dados.</p>

            <form onSubmit={handleUpdateAmse}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '4px' }}>Usuário</label>
                <input
                  type="text"
                  value={amseCreds.user}
                  onChange={e => setAmseCreds({ ...amseCreds, user: e.target.value })}
                  style={{ width: '100%', padding: '8px', background: '#333', border: '1px solid #555', color: 'white' }}
                  required
                />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', marginBottom: '4px' }}>Senha</label>
                <input
                  type="password"
                  value={amseCreds.password}
                  onChange={e => setAmseCreds({ ...amseCreds, password: e.target.value })}
                  style={{ width: '100%', padding: '8px', background: '#333', border: '1px solid #555', color: 'white' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                <button type="button" onClick={() => setShowAmseModal(false)} style={{ background: 'transparent', border: '1px solid #555' }} disabled={isAmseRunning}>
                  Cancelar
                </button>
                <button type="submit" style={{ background: '#2563eb' }} disabled={isAmseRunning}>
                  {isAmseRunning ? 'Rodando...' : 'Iniciar Atualização'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SCHEDULE MODAL */}
      <ScheduleModal
        show={showScheduleModal}
        onClose={() => setShowScheduleModal(false)}
        configId={scheduledConfigId}
        label={scheduledConfigLabel}
      />

      {/* DETAILS MODAL (AMSE STYLE) */}
      {viewingTransmissora && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
          background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
        }}>
          <div style={{
            width: '95%', maxWidth: '1000px', maxHeight: '95vh', overflowY: 'auto',
            background: '#fff', boxShadow: '0 0 20px rgba(0,0,0,0.3)',
            fontFamily: 'Arial, sans-serif', color: '#333', fontSize: '13px',
            padding: '20px'
          }}>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', background: '#f5f5f5', padding: '10px', borderBottom: '1px solid #ddd' }}>
              <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ fontWeight: 'bold' }}>Código</span>
                  <div style={{ border: '1px solid #84cc16', padding: '2px 10px', fontWeight: 'bold', color: '#000', background: '#fff' }}>{viewingTransmissora.codigo_ons}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ fontWeight: 'bold' }}>Sigla</span>
                  <div style={{ border: '1px solid #84cc16', padding: '2px 10px', fontWeight: 'bold', color: '#000', background: '#fff' }}>{viewingTransmissora.sigla}</div>
                </div>
              </div>
              <button
                onClick={() => setViewingTransmissora(null)}
                style={{
                  background: '#ef4444', color: 'white', border: 'none',
                  padding: '5px 15px', fontWeight: 'bold', fontSize: '12px',
                  borderRadius: '4px', cursor: 'pointer', textTransform: 'uppercase',
                  boxShadow: 'none'
                }}
              >
                FECHAR
              </button>
            </div>

            {(() => {
              const data = JSON.parse(viewingTransmissora.dados_json || '{}')

              // Helper to safely get value checking multiple keys/cases
              const getVal = (keys) => {
                if (!keys) return null;
                if (!Array.isArray(keys)) keys = [keys];
                for (const k of keys) {
                  try {
                    // Try Exact
                    if (data[k] !== undefined && data[k] !== null && data[k] !== "" && String(data[k]) !== "nan" && String(data[k]) !== "undefined") return data[k];
                    // Try Upper (Robot output)
                    const kUp = k.toUpperCase().replace(/_/g, ' ');
                    if (data[kUp] !== undefined && data[kUp] !== null && data[kUp] !== "" && String(data[kUp]) !== "nan") return data[kUp];
                    // Try Raw Upper
                    const kRaw = k.toUpperCase();
                    if (data[kRaw] !== undefined && data[kRaw] !== null && data[kRaw] !== "" && String(data[kRaw]) !== "nan") return data[kRaw];
                  } catch (e) { return null }
                }
                return null;
              }

              const SectionTitle = ({ title }) => (
                <h3 style={{
                  color: '#65a30d', borderBottom: '1px solid #65a30d',
                  paddingBottom: '2px', marginTop: '15px', marginBottom: '10px',
                  fontSize: '12px', textTransform: 'uppercase', fontWeight: 'bold',
                  letterSpacing: '0.5px'
                }}>
                  {title}
                </h3>
              )

              const Field = ({ label, value, full = false }) => (
                <div style={{ display: 'flex', flexDirection: 'column', marginBottom: '5px', width: full ? '100%' : 'auto' }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '5px' }}>
                    <span style={{ fontWeight: 'bold', fontSize: '11px', color: '#000', minWidth: 'fit-content' }}>{label}:</span>
                    <span style={{ fontSize: '11px', color: '#333' }}>{value && value !== 'undefined' ? value : '-'}</span>
                  </div>
                </div>
              )

              const Box = ({ children }) => (
                <div style={{ border: '1px solid #ccc', padding: '10px 15px', marginBottom: '5px', background: '#fff' }}>
                  {children}
                </div>
              )

              // Computed Values
              const bancoName = getVal(['banco', 'BANCO']);
              const bancoNum = getVal(['numero_do_banco', 'NUMERO DO BANCO']);
              const bancoDisplay = bancoName ? (bancoNum ? `${bancoName} (${bancoNum})` : bancoName) : '-';

              const logradouro = getVal(['logradouro', 'LOGRADOURO']) || '';
              const num = getVal(['numero', 'NUMERO']) || '';
              const comp = getVal(['complemento', 'COMPLEMENTO']) || '';

              return (
                <div style={{ padding: '5px' }}>
                  <SectionTitle title="VINCULAÇÃO AO SACT" />
                  <Box>
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '20px' }}>
                      <Field label="Agente SACT" value={viewingTransmissora.sigla} />
                      <Field label="Concessão" value={getVal(['concessao', 'CONCESSÃO'])} />
                      <Field label="Data" value={getVal(['dt_concessao', 'DT CONCESSÃO'])} />
                    </div>
                    <div style={{ marginTop: '5px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                      <Field label="Contrato" value={getVal(['contrato', 'CONTRATO'])} />
                      <Field label="Termo Aditivo Vigente" value={getVal(['termo_aditivo', 'TERMO ADITIVO']) || '-'} />
                    </div>
                  </Box>

                  <SectionTitle title="DADOS GERAIS" />
                  <Box>
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '20px' }}>
                      <Field label="Responsável" value={getVal(['nome_do_representante', 'NOME DO REPRESENTANTE'])} />
                      <div style={{ display: 'flex', gap: '5px', alignItems: 'center' }}>
                        <span style={{ fontWeight: 'bold', fontSize: '11px' }}>Status:</span>
                        <span style={{ color: 'green', fontWeight: 'bold', fontSize: '11px' }}>Ativo</span>
                      </div>
                      <Field label="Classificação" value={getVal(['classificacao_empresa', 'CLASSIFICAÇÃO EMPRESA']) || viewingTransmissora.grupo} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '5px' }}>
                      <Field label="Início Contábil" value={getVal(['dt_inicio_contabil', 'DT INICIO CONTÁBIL'])} />
                      <Field label="Operação" value={getVal(['dt_inicio_operacao', 'DT INICIO OPERAÇÃO'])} />
                    </div>
                  </Box>

                  <SectionTitle title="DADOS DO AGENTE" />
                  <Box>
                    <div style={{ marginBottom: '5px' }}><Field label="Razão Social" value={getVal(['razao_social', 'RAZÃO SOCIAL']) || viewingTransmissora.nome} full /></div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
                      <Field label="CNPJ" value={viewingTransmissora.cnpj} />
                      <Field label="Inscrição Estadual" value={getVal(['inscricao_estadual', 'INSCRIÇÃO ESTADUAL'])} />
                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <div style={{ width: '12px', height: '12px', background: '#555', borderRadius: '2px' }}></div>
                        <span style={{ fontSize: '11px', color: '#555' }}>Padrão Desligamento</span>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '3fr 1fr', gap: '20px', marginTop: '5px' }}>
                      <Field label="Logradouro" value={logradouro} />
                      <Field label="Número" value={num} />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '20px', marginTop: '5px' }}>
                      <div style={{ display: 'flex', gap: '20px' }}>
                        <Field label="Complemento" value={comp} />
                      </div>
                      <Field label="Bairro" value={getVal(['bairro', 'BAIRRO'])} />
                      <Field label="CEP" value={getVal(['cep', 'CEP'])} />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'min-content 1fr 1fr', gap: '20px', marginTop: '5px', alignItems: 'baseline' }}>
                      <Field label="Estado" value={getVal(['uf', 'UF'])} />
                      <Field label="Cidade" value={getVal(['cidade', 'CIDADE'])} />
                      <Field label="Região" value={getVal(['regiao', 'REGIÃO'])} />
                    </div>
                  </Box>

                  <SectionTitle title="DADOS BANCÁRIOS" />
                  <Box>
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '20px' }}>
                      <Field label="Banco" value={bancoDisplay} />
                      <Field label="Agência" value={getVal(['agencia', 'AGENCIA'])} />
                      <Field label="Conta" value={getVal(['conta', 'CONTA'])} />
                    </div>
                  </Box>

                  <SectionTitle title="DADOS FISCAIS" />
                  <Box>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
                      <Field label="PIS/COFINS %" value={getVal(['%_aliquota_pis_confins', '% ALIQUOTA PIS CONFINS'])} />
                      <Field label="Aliquota RGR %" value={getVal(['%_aliquota_rgr', '% ALIQUOTA RGR'])} />
                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <div style={{ width: '12px', height: '12px', background: '#555', borderRadius: '2px' }}></div>
                        <span style={{ fontSize: '11px', color: '#555' }}>Incluir PIS/COFINS</span>
                      </div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '5px' }}>
                      <Field label="RAP RB %" value="-" />
                      <Field label="RAP RF %" value="-" />
                    </div>
                  </Box>

                  <SectionTitle title="ENCAMINHAMENTO DAS FATURAS" />
                  <Box>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 3fr', gap: '20px' }}>
                      <Field label="Forma" value={getVal(['forma_de_encaminhamento_das_fat', 'FORMA DE ENCAMINHAMENTO DAS FAT'])} />
                      <Field label="URL do Site" value={getVal(['url_do_site', 'URL DO SITE'])} />
                    </div>
                  </Box>

                  <SectionTitle title="REPRESENTANTES" />
                  <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '5px', fontSize: '11px' }}>
                    <thead>
                      <tr style={{ background: '#84cc16', color: 'white', textAlign: 'left' }}>
                        <th style={{ padding: '5px' }}>NOME</th>
                        <th style={{ padding: '5px' }}>TELEFONE</th>
                        <th style={{ padding: '5px' }}>E-MAIL</th>
                        <th style={{ padding: '5px' }}>FUNÇÕES</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr style={{ borderBottom: '1px solid #eee' }}>
                        <td style={{ padding: '5px' }}>{getVal(['nome_do_representante', 'NOME DO REPRESENTANTE']) || '-'}</td>
                        <td style={{ padding: '5px' }}>{getVal(['telefone', 'TELEFONE']) || '-'}</td>
                        <td style={{ padding: '5px' }}>{getVal(['email', 'E-MAIL']) || '-'}</td>
                        <td style={{ padding: '5px' }}>{getVal(['funcao_do_representante', 'FUNÇÃO DO REPRESENTANTE']) || '-'}</td>
                      </tr>
                      {data['representantes_list'] && data['representantes_list'].length > 0 && data['representantes_list'].map((rep, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid #eee' }}>
                          <td style={{ padding: '5px' }}>{rep.nome}</td>
                          <td style={{ padding: '5px' }}>{rep.telefone}</td>
                          <td style={{ padding: '5px' }}>{rep.email}</td>
                          <td style={{ padding: '5px' }}>{rep.funcao}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>


                </div>
              )
            })()}
          </div>
        </div>
      )}
    </div >
  )
}

export default App
