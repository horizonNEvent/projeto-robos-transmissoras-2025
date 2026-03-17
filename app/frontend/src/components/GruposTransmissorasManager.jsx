import { useState, useEffect, useMemo } from 'react'
import axios from 'axios'

const API_URL = '/api'

// Paleta de cores por grupo (fixada para poucos; resto usa hash)
const GROUP_COLORS = {
  'SigetPlus':   { bg: 'rgba(99,102,241,0.15)',  border: '#6366f1', badge: '#6366f1' },
  'Glorian':     { bg: 'rgba(16,185,129,0.15)',   border: '#10b981', badge: '#10b981' },
  'Light':       { bg: 'rgba(245,158,11,0.15)',   border: '#f59e0b', badge: '#f59e0b' },
  'Equatorial':  { bg: 'rgba(59,130,246,0.15)',   border: '#3b82f6', badge: '#3b82f6' },
  'Harpix':      { bg: 'rgba(236,72,153,0.15)',   border: '#ec4899', badge: '#ec4899' },
  'CEEE':        { bg: 'rgba(168,85,247,0.15)',    border: '#a855f7', badge: '#a855f7' },
  'I.E':         { bg: 'rgba(20,184,166,0.15)',    border: '#14b8a6', badge: '#14b8a6' },
  'AXIA':        { bg: 'rgba(239,68,68,0.15)',     border: '#ef4444', badge: '#ef4444' },
  'Celeo':       { bg: 'rgba(251,146,60,0.15)',    border: '#fb923c', badge: '#fb923c' },
  'Neoenergia':  { bg: 'rgba(34,197,94,0.15)',     border: '#22c55e', badge: '#22c55e' },
  'Cemig':       { bg: 'rgba(234,179,8,0.15)',     border: '#eab308', badge: '#eab308' },
  'Copel':       { bg: 'rgba(14,165,233,0.15)',    border: '#0ea5e9', badge: '#0ea5e9' },
  'TBE':         { bg: 'rgba(132,204,22,0.15)',    border: '#84cc16', badge: '#84cc16' },
  'Alupar':      { bg: 'rgba(249,115,22,0.15)',    border: '#f97316', badge: '#f97316' },
  'Energisa':    { bg: 'rgba(217,70,239,0.15)',    border: '#d946ef', badge: '#d946ef' },
  'Grupo CPFL':  { bg: 'rgba(99,179,237,0.15)',    border: '#63b3ed', badge: '#63b3ed' },
  'Zopone':      { bg: 'rgba(160,210,180,0.15)',   border: '#a0d2b4', badge: '#a0d2b4' },
  'ONS':         { bg: 'rgba(100,116,139,0.15)',   border: '#64748b', badge: '#64748b' },
  'Rialma V':    { bg: 'rgba(251,191,36,0.15)',    border: '#fbbf24', badge: '#fbbf24' },
}

function hashColor(str) {
  let hash = 0
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash)
  const h = Math.abs(hash) % 360
  return { bg: `hsla(${h},60%,55%,0.15)`, border: `hsl(${h},60%,55%)`, badge: `hsl(${h},60%,55%)` }
}

function getGroupColor(grupo) {
  return GROUP_COLORS[grupo] || hashColor(grupo)
}

export default function GruposTransmissorasManager({ onLog }) {
  const [entries, setEntries]           = useState([])
  const [groupNames, setGroupNames]     = useState([])
  const [loading, setLoading]           = useState(true)
  const [seeding, setSeeding]           = useState(false)
  const [viewMode, setViewMode]         = useState('tabela') // 'tabela' | 'grupos'

  // Filtros
  const [fGrupo, setFGrupo]             = useState('')
  const [fONS, setFONS]                 = useState('')
  const [fNome, setFNome]               = useState('')
  const [fCNPJ, setFCNPJ]               = useState('')

  // Modal Adicionar
  const [showAdd, setShowAdd]           = useState(false)
  const [addForm, setAddForm]           = useState({ grupo: '', portal_url: '', codigo_ons: '', nome_transmissora: '', cnpj: '' })
  const [addLoading, setAddLoading]     = useState(false)
  const [addError, setAddError]         = useState('')

  // Modal Editar
  const [editEntry, setEditEntry]       = useState(null)
  const [editForm, setEditForm]         = useState({})
  const [editLoading, setEditLoading]   = useState(false)

  // Confirmação Remover
  const [removeId, setRemoveId]         = useState(null)

  const log = (msg) => onLog && onLog(msg)

  const fetchAll = async () => {
    try {
      setLoading(true)
      const [dataRes, namesRes] = await Promise.all([
        axios.get(`${API_URL}/grupos`),
        axios.get(`${API_URL}/grupos/nomes`)
      ])
      setEntries(dataRes.data)
      setGroupNames(namesRes.data)
    } catch (e) {
      log('Erro ao carregar grupos: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchAll() }, [])

  const filtered = useMemo(() => entries.filter(e => {
    const gOk   = !fGrupo || e.grupo?.toLowerCase().includes(fGrupo.toLowerCase())
    const onsOk = !fONS   || e.codigo_ons?.includes(fONS)
    const nOk   = !fNome  || e.nome_transmissora?.toLowerCase().includes(fNome.toLowerCase())
    const cOk   = !fCNPJ  || e.cnpj?.toLowerCase().includes(fCNPJ.toLowerCase())
    return gOk && onsOk && nOk && cOk
  }), [entries, fGrupo, fONS, fNome, fCNPJ])

  // Agrupar para view "grupos"
  const grouped = useMemo(() => {
    const map = {}
    filtered.forEach(e => {
      if (!map[e.grupo]) map[e.grupo] = { portal_url: e.portal_url, items: [] }
      map[e.grupo].items.push(e)
    })
    return map
  }, [filtered])

  const handleSeed = async () => {
    if (!window.confirm('Isso irá popular o banco com os dados do CSV inicial. Continuar?')) return
    try {
      setSeeding(true)
      const res = await axios.post(`${API_URL}/grupos/seed`)
      log(res.data.message)
      alert(res.data.message)
      fetchAll()
    } catch (e) {
      const msg = e.response?.data?.detail || e.message
      log('Erro seed: ' + msg)
      alert('Erro: ' + msg)
    } finally {
      setSeeding(false)
    }
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    setAddError('')
    if (!addForm.grupo || !addForm.codigo_ons) {
      setAddError('Grupo e Código ONS são obrigatórios.')
      return
    }
    try {
      setAddLoading(true)
      await axios.post(`${API_URL}/grupos`, addForm)
      log(`Transmissora ONS ${addForm.codigo_ons} adicionada ao grupo ${addForm.grupo}`)
      setShowAdd(false)
      setAddForm({ grupo: '', portal_url: '', codigo_ons: '', nome_transmissora: '', cnpj: '' })
      fetchAll()
    } catch (err) {
      setAddError(err.response?.data?.detail || err.message)
    } finally {
      setAddLoading(false)
    }
  }

  const handleOpenEdit = (entry) => {
    setEditEntry(entry)
    setEditForm({ grupo: entry.grupo, portal_url: entry.portal_url || '', nome_transmissora: entry.nome_transmissora || '', cnpj: entry.cnpj || '' })
  }

  const handleEdit = async (e) => {
    e.preventDefault()
    try {
      setEditLoading(true)
      await axios.put(`${API_URL}/grupos/${editEntry.id}`, editForm)
      log(`Registro #${editEntry.id} atualizado`)
      setEditEntry(null)
      fetchAll()
    } catch (err) {
      alert(err.response?.data?.detail || err.message)
    } finally {
      setEditLoading(false)
    }
  }

  const handleRemove = async () => {
    try {
      await axios.delete(`${API_URL}/grupos/${removeId}`)
      log(`Registro #${removeId} removido`)
      setRemoveId(null)
      fetchAll()
    } catch (err) {
      alert(err.response?.data?.detail || err.message)
    }
  }

  const inputStyle = {
    background: '#1e293b', border: '1px solid #334155', color: 'white',
    padding: '0.5rem 0.75rem', borderRadius: '6px', width: '100%', fontSize: '0.85rem'
  }
  const labelStyle = { fontSize: '0.7rem', color: '#94a3b8', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }

  return (
    <div style={{ padding: '0 0 2rem 0' }}>
      {/* HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>🏢 Grupos de Transmissoras</h2>
          <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '0.85rem' }}>
            {entries.length} vínculos · {groupNames.length} grupos
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Toggle view */}
          <div style={{ display: 'flex', background: '#1e293b', borderRadius: '8px', padding: '4px', border: '1px solid #334155' }}>
            {['tabela', 'grupos'].map(v => (
              <button key={v} onClick={() => setViewMode(v)} style={{
                background: viewMode === v ? 'var(--accent)' : 'transparent',
                border: 'none', color: viewMode === v ? '#fff' : '#64748b',
                padding: '0.35rem 0.9rem', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600
              }}>
                {v === 'tabela' ? '📋 Tabela' : '🗂️ Por Grupo'}
              </button>
            ))}
          </div>
          <button onClick={() => setShowAdd(true)} style={{ background: 'var(--accent)', border: 'none', color: '#fff', padding: '0.5rem 1.2rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
            ➕ Adicionar
          </button>
          <button onClick={handleSeed} disabled={seeding} style={{ background: seeding ? '#334155' : '#0f766e', border: 'none', color: '#fff', padding: '0.5rem 1.2rem', borderRadius: '8px', cursor: seeding ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
            {seeding ? '⏳ Importando...' : '📥 Importar CSV Inicial'}
          </button>
        </div>
      </div>

      {/* FILTROS */}
      <div className="card" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem', padding: '1rem' }}>
        <div>
          <label style={labelStyle}>Grupo</label>
          <select value={fGrupo} onChange={e => setFGrupo(e.target.value)} style={inputStyle}>
            <option value="">Todos</option>
            {groupNames.map(g => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
        <div>
          <label style={labelStyle}>Cód. ONS</label>
          <input placeholder="Ex: 1020" value={fONS} onChange={e => setFONS(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Nome Transmissora</label>
          <input placeholder="Buscar..." value={fNome} onChange={e => setFNome(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>CNPJ</label>
          <input placeholder="00.000..." value={fCNPJ} onChange={e => setFCNPJ(e.target.value)} style={inputStyle} />
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⏳</div>
          Carregando grupos...
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#64748b', border: '1px dashed #334155', borderRadius: '12px' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📭</div>
          Nenhum registro encontrado.{entries.length === 0 && <> Clique em <b>"Importar CSV Inicial"</b> para popular os dados.</>}
        </div>
      ) : viewMode === 'tabela' ? (
        /* ---- VIEW TABELA ---- */
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid #1e293b' }}>
                  {['Grupo','Portal','Cód. ONS','Nome Transmissora','CNPJ','Ações'].map(h => (
                    <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 700, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((row, i) => {
                  const col = getGroupColor(row.grupo)
                  return (
                    <tr key={row.id} style={{ borderBottom: '1px solid #0f172a', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}>
                      <td style={{ padding: '0.65rem 1rem' }}>
                        <span style={{ background: col.bg, border: `1px solid ${col.border}`, color: col.badge, borderRadius: '999px', padding: '2px 10px', fontSize: '0.75rem', fontWeight: 700, whiteSpace: 'nowrap' }}>
                          {row.grupo}
                        </span>
                      </td>
                      <td style={{ padding: '0.65rem 1rem', fontSize: '0.75rem' }}>
                        {row.portal_url
                          ? <a href={row.portal_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', textDecoration: 'none' }} title={row.portal_url}>🔗 Abrir</a>
                          : <span style={{ color: '#475569' }}>—</span>}
                      </td>
                      <td style={{ padding: '0.65rem 1rem', fontWeight: 700, color: 'var(--accent)', fontFamily: 'monospace' }}>{row.codigo_ons}</td>
                      <td style={{ padding: '0.65rem 1rem', fontSize: '0.82rem', maxWidth: '320px' }}>{row.nome_transmissora || '—'}</td>
                      <td style={{ padding: '0.65rem 1rem', fontSize: '0.78rem', color: '#94a3b8', fontFamily: 'monospace' }}>{row.cnpj || '—'}</td>
                      <td style={{ padding: '0.65rem 1rem', whiteSpace: 'nowrap' }}>
                        <button onClick={() => handleOpenEdit(row)} title="Editar" style={{ background: 'rgba(59,130,246,0.15)', border: '1px solid #3b82f6', color: '#3b82f6', borderRadius: '6px', padding: '3px 10px', cursor: 'pointer', fontSize: '0.78rem', marginRight: '4px' }}>✏️</button>
                        <button onClick={() => setRemoveId(row.id)} title="Remover" style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid #ef4444', color: '#ef4444', borderRadius: '6px', padding: '3px 10px', cursor: 'pointer', fontSize: '0.78rem' }}>🗑️</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div style={{ padding: '0.75rem 1rem', borderTop: '1px solid #1e293b', color: '#64748b', fontSize: '0.78rem' }}>
            Exibindo {filtered.length} de {entries.length} registros
          </div>
        </div>
      ) : (
        /* ---- VIEW POR GRUPOS ---- */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1rem' }}>
          {Object.entries(grouped).map(([grupo, { portal_url, items }]) => {
            const col = getGroupColor(grupo)
            return (
              <div key={grupo} style={{ background: col.bg, border: `1px solid ${col.border}`, borderRadius: '12px', overflow: 'hidden' }}>
                {/* Card header */}
                <div style={{ padding: '0.85rem 1rem', borderBottom: `1px solid ${col.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: '0.95rem', color: col.badge }}>{grupo}</div>
                    {portal_url && (
                      <a href={portal_url} target="_blank" rel="noreferrer" style={{ fontSize: '0.7rem', color: '#94a3b8', textDecoration: 'none' }} title={portal_url}>
                        🔗 {new URL(portal_url).hostname}
                      </a>
                    )}
                  </div>
                  <span style={{ background: col.badge, color: '#fff', borderRadius: '999px', padding: '2px 10px', fontSize: '0.72rem', fontWeight: 700 }}>
                    {items.length} transmissora{items.length !== 1 ? 's' : ''}
                  </span>
                </div>
                {/* Rows */}
                <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                  {items.map(item => (
                    <div key={item.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 1rem', borderBottom: '1px solid rgba(255,255,255,0.04)', gap: '0.5rem' }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', fontWeight: 700, color: col.badge, whiteSpace: 'nowrap' }}>#{item.codigo_ons}</span>
                          <span style={{ fontSize: '0.78rem', color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.nome_transmissora || '—'}</span>
                        </div>
                        {item.cnpj && <div style={{ fontSize: '0.68rem', color: '#64748b', fontFamily: 'monospace', marginTop: '1px' }}>{item.cnpj}</div>}
                      </div>
                      <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
                        <button onClick={() => handleOpenEdit(item)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '0.85rem', padding: '2px' }} title="Editar">✏️</button>
                        <button onClick={() => setRemoveId(item.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '0.85rem', padding: '2px' }} title="Remover">🗑️</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ===== MODAL ADICIONAR ===== */}
      {showAdd && (
        <ModalOverlay onClose={() => setShowAdd(false)}>
          <h3 style={{ margin: '0 0 1.25rem', fontSize: '1.1rem' }}>➕ Adicionar Transmissora a Grupo</h3>
          {addError && <div style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid #ef4444', color: '#fca5a5', borderRadius: '8px', padding: '0.6rem 0.9rem', marginBottom: '1rem', fontSize: '0.82rem' }}>{addError}</div>}
          <form onSubmit={handleAdd}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
              <div>
                <label style={labelStyle}>Grupo *</label>
                <input list="grupo-list" placeholder="Ex: TBE" value={addForm.grupo} onChange={e => setAddForm({ ...addForm, grupo: e.target.value })} style={inputStyle} required />
                <datalist id="grupo-list">{groupNames.map(g => <option key={g} value={g} />)}</datalist>
              </div>
              <div>
                <label style={labelStyle}>Código ONS *</label>
                <input placeholder="Ex: 1020" value={addForm.codigo_ons} onChange={e => setAddForm({ ...addForm, codigo_ons: e.target.value })} style={inputStyle} required />
              </div>
            </div>
            <div style={{ marginBottom: '0.75rem' }}>
              <label style={labelStyle}>Nome da Transmissora</label>
              <input placeholder="Ex: LIGHT" value={addForm.nome_transmissora} onChange={e => setAddForm({ ...addForm, nome_transmissora: e.target.value })} style={inputStyle} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div>
                <label style={labelStyle}>CNPJ</label>
                <input placeholder="00.000.000/0001-00" value={addForm.cnpj} onChange={e => setAddForm({ ...addForm, cnpj: e.target.value })} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>URL do Portal</label>
                <input placeholder="https://..." value={addForm.portal_url} onChange={e => setAddForm({ ...addForm, portal_url: e.target.value })} style={inputStyle} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button type="button" onClick={() => setShowAdd(false)} style={{ background: 'transparent', border: '1px solid #334155', color: '#94a3b8', padding: '0.5rem 1.25rem', borderRadius: '8px', cursor: 'pointer' }}>Cancelar</button>
              <button type="submit" disabled={addLoading} style={{ background: 'var(--accent)', border: 'none', color: '#fff', padding: '0.5rem 1.5rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>
                {addLoading ? 'Salvando...' : 'Salvar'}
              </button>
            </div>
          </form>
        </ModalOverlay>
      )}

      {/* ===== MODAL EDITAR ===== */}
      {editEntry && (
        <ModalOverlay onClose={() => setEditEntry(null)}>
          <h3 style={{ margin: '0 0 0.5rem', fontSize: '1.1rem' }}>✏️ Editar Registro</h3>
          <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '8px', padding: '0.6rem 0.9rem', marginBottom: '1.25rem', fontSize: '0.82rem', color: '#94a3b8' }}>
            ONS: <strong style={{ color: '#e2e8f0' }}>{editEntry.codigo_ons}</strong>
          </div>
          <form onSubmit={handleEdit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
              <div>
                <label style={labelStyle}>Grupo</label>
                <input list="grupo-list-edit" value={editForm.grupo} onChange={e => setEditForm({ ...editForm, grupo: e.target.value })} style={inputStyle} />
                <datalist id="grupo-list-edit">{groupNames.map(g => <option key={g} value={g} />)}</datalist>
              </div>
              <div>
                <label style={labelStyle}>Nome Transmissora</label>
                <input value={editForm.nome_transmissora} onChange={e => setEditForm({ ...editForm, nome_transmissora: e.target.value })} style={inputStyle} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div>
                <label style={labelStyle}>CNPJ</label>
                <input value={editForm.cnpj} onChange={e => setEditForm({ ...editForm, cnpj: e.target.value })} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>URL do Portal</label>
                <input value={editForm.portal_url} onChange={e => setEditForm({ ...editForm, portal_url: e.target.value })} style={inputStyle} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button type="button" onClick={() => setEditEntry(null)} style={{ background: 'transparent', border: '1px solid #334155', color: '#94a3b8', padding: '0.5rem 1.25rem', borderRadius: '8px', cursor: 'pointer' }}>Cancelar</button>
              <button type="submit" disabled={editLoading} style={{ background: '#3b82f6', border: 'none', color: '#fff', padding: '0.5rem 1.5rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>
                {editLoading ? 'Salvando...' : 'Atualizar'}
              </button>
            </div>
          </form>
        </ModalOverlay>
      )}

      {/* ===== MODAL CONFIRMAR REMOÇÃO ===== */}
      {removeId && (
        <ModalOverlay onClose={() => setRemoveId(null)}>
          <div style={{ textAlign: 'center', padding: '0.5rem' }}>
            <div style={{ fontSize: '3rem', marginBottom: '0.75rem' }}>⚠️</div>
            <h3 style={{ margin: '0 0 0.5rem' }}>Confirmar Remoção</h3>
            <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginBottom: '1.5rem' }}>
              Tem certeza que deseja remover o registro <strong>#{removeId}</strong>? Essa ação não pode ser desfeita.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem' }}>
              <button onClick={() => setRemoveId(null)} style={{ background: 'transparent', border: '1px solid #334155', color: '#94a3b8', padding: '0.5rem 1.5rem', borderRadius: '8px', cursor: 'pointer' }}>Cancelar</button>
              <button onClick={handleRemove} style={{ background: '#ef4444', border: 'none', color: '#fff', padding: '0.5rem 1.5rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}>Remover</button>
            </div>
          </div>
        </ModalOverlay>
      )}
    </div>
  )
}

function ModalOverlay({ children, onClose }) {
  return (
    <div
      onClick={e => e.target === e.currentTarget && onClose()}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999, padding: '1rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: '560px', position: 'relative', maxHeight: '90vh', overflowY: 'auto' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: '0.75rem', right: '0.75rem', background: 'transparent', border: 'none', color: '#64748b', fontSize: '1.3rem', cursor: 'pointer', lineHeight: 1 }}>&times;</button>
        {children}
      </div>
    </div>
  )
}
