import React, { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = `http://${window.location.hostname}:8000`

export default function SigetPublicManager({ onLog }) {
    const [targets, setTargets] = useState([])
    const [loading, setLoading] = useState(false)

    // Form para adicionar
    const [newCode, setNewCode] = useState('')
    const [newName, setNewName] = useState('')
    const [searchTransmissora, setSearchTransmissora] = useState('')
    const [transmissorasBase, setTransmissorasBase] = useState([])

    useEffect(() => {
        fetchTargets()
        fetchTransmissorasBase()
    }, [])

    const fetchTargets = async () => {
        setLoading(true)
        try {
            const res = await axios.get(`${API_URL}/siget-public/targets`)
            setTargets(res.data)
        } catch (err) {
            console.error(err)
            onLog && onLog(`Erro ao buscar targets: ${err.message}`)
        } finally {
            setLoading(false)
        }
    }

    const fetchTransmissorasBase = async () => {
        try {
            const res = await axios.get(`${API_URL}/transmissoras`)
            setTransmissorasBase(res.data || [])
        } catch (err) { console.error(err) }
    }

    const handleAdd = async () => {
        if (!newCode || !newName) {
            alert("Preencha Código ONS e Nome.")
            return
        }
        try {
            await axios.post(`${API_URL}/siget-public/targets`, {
                codigo_ons: newCode,
                nome: newName,
                ativo: true
            })
            fetchTargets()
            setNewCode('')
            setNewName('')
            setSearchTransmissora('')
            onLog && onLog(`Target ${newName} adicionado com sucesso.`)
        } catch (err) {
            alert("Erro ao adicionar: " + (err.response?.data?.detail || err.message))
        }
    }

    const handleToggle = async (id, currentStatus) => {
        try {
            await axios.put(`${API_URL}/siget-public/targets/${id}/toggle`)
            fetchTargets()
        } catch (err) { console.error(err) }
    }

    const handleDelete = async (id) => {
        if (!confirm("Tem certeza que deseja remover este alvo?")) return
        try {
            await axios.delete(`${API_URL}/siget-public/targets/${id}`)
            fetchTargets()
            onLog && onLog(`Target removido.`)
        } catch (err) { console.error(err) }
    }

    // Filtrar transmissoras base para autocomplete
    const filteredBase = transmissorasBase.filter(t =>
        (t.nome && t.nome.toLowerCase().includes(searchTransmissora.toLowerCase())) ||
        (t.codigo_ons && t.codigo_ons.includes(searchTransmissora))
    ).slice(0, 10)

    return (
        <div className="card">
            <h3>Gerenciador de Alvos (WebSigetPublic)</h3>
            <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
                Defina quais transmissoras o robô WebSigetPublic deve processar.
            </p>

            {/* Form de Adição */}
            <div style={{ background: 'rgba(255,255,255,0.05)', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', border: '1px dashed #475569' }}>
                <h4 style={{ margin: '0 0 1rem 0' }}>Adicionar Nova Transmissora ao Robô</h4>

                {/* Busca na Base */}
                <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8' }}>Buscar na Base de Transmissoras (Opcional)</label>
                    <input
                        placeholder="Digite nome ou código ONS..."
                        value={searchTransmissora}
                        onChange={e => setSearchTransmissora(e.target.value)}
                        style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #334155', background: '#1e293b', color: 'white' }}
                    />
                    {searchTransmissora && (
                        <div style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '4px', marginTop: '4px', maxHeight: '150px', overflowY: 'auto' }}>
                            {filteredBase.map(t => (
                                <div
                                    key={t.id}
                                    style={{ padding: '0.5rem', cursor: 'pointer', borderBottom: '1px solid #1e293b', fontSize: '0.8rem' }}
                                    onClick={() => {
                                        setNewCode(t.codigo_ons)
                                        setNewName(t.nome)
                                        setSearchTransmissora('')
                                    }}
                                >
                                    <strong>{t.codigo_ons}</strong> - {t.nome}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div style={{ display: 'flex', gap: '1rem' }}>
                    <div style={{ flex: 1 }}>
                        <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8' }}>Código ONS *</label>
                        <input
                            value={newCode}
                            onChange={e => setNewCode(e.target.value)}
                            placeholder="Ex: 3748"
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #334155', background: '#1e293b', color: 'white' }}
                        />
                    </div>
                    <div style={{ flex: 3 }}>
                        <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8' }}>Nome da Transmissora *</label>
                        <input
                            value={newName}
                            onChange={e => setNewName(e.target.value)}
                            placeholder="Nome descritivo"
                            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #334155', background: '#1e293b', color: 'white' }}
                        />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'end' }}>
                        <button onClick={handleAdd} style={{ background: '#10b981', height: '38px' }}>
                            + Adicionar
                        </button>
                    </div>
                </div>
            </div>

            {/* Lista com Scroll */}
            <div style={{ overflowX: 'auto', maxHeight: '400px', overflowY: 'auto', border: '1px solid #334155', borderRadius: '4px' }} className="custom-scroll">
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead style={{ position: 'sticky', top: 0, background: '#0f172a', zIndex: 1 }}>
                        <tr style={{ borderBottom: '2px solid #334155', color: '#94a3b8', fontSize: '0.8rem', textAlign: 'left' }}>
                            <th style={{ padding: '0.5rem' }}>O.N.S</th>
                            <th style={{ padding: '0.5rem' }}>Nome</th>
                            <th style={{ padding: '0.5rem' }}>Status</th>
                            <th style={{ padding: '0.5rem', textAlign: 'right' }}>Ações</th>
                        </tr>
                    </thead>
                    <tbody>
                        {targets.map(t => (
                            <tr key={t.id} style={{ borderBottom: '1px solid #1e293b' }}>
                                <td style={{ padding: '0.5rem' }}>{t.codigo_ons}</td>
                                <td style={{ padding: '0.5rem', fontWeight: 'bold' }}>{t.nome}</td>
                                <td style={{ padding: '0.5rem' }}>
                                    <span
                                        style={{
                                            padding: '2px 8px', borderRadius: '12px', fontSize: '0.7rem', fontWeight: 'bold',
                                            background: t.ativo ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                            color: t.ativo ? '#10b981' : '#ef4444'
                                        }}
                                    >
                                        {t.ativo ? 'ATIVO' : 'INATIVO'}
                                    </span>
                                </td>
                                <td style={{ padding: '0.5rem', textAlign: 'right', display: 'flex', gap: '0.5rem', justifyContent: 'end' }}>
                                    <button
                                        onClick={() => handleToggle(t.id, t.ativo)}
                                        style={{ padding: '4px 8px', fontSize: '0.7rem', background: '#3b82f6' }}
                                    >
                                        {t.ativo ? 'Desativar' : 'Ativar'}
                                    </button>
                                    <button
                                        onClick={() => handleDelete(t.id)}
                                        style={{ padding: '4px 8px', fontSize: '0.7rem', background: '#ef4444' }}
                                    >
                                        Remover
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {targets.length === 0 && (
                            <tr>
                                <td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                                    Nenhuma transmissora configurada.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}
