import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = "/api";

// Ícones Customizados SVG (Estilo Corporate)
const IconEye = ({ size = 18 }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
const IconDownload = ({ size = 18 }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
const IconRefresh = ({ animate, size = 18 }) => <svg width={size} height={size} className={animate ? 'animate-spin' : ''} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></svg>
const IconFileXml = ({ size = 18 }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><path d="M8 13h1" /><path d="M8 17h1" /><path d="M12 13h4" /><path d="M12 17h4" /></svg>
const IconTrash = ({ size = 18 }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" /></svg>

const DocumentManager = () => {
    const [docs, setDocs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [filter, setFilter] = useState("");
    const [selectedDoc, setSelectedDoc] = useState(null);

    const fetchDocs = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_URL}/documents`);
            setDocs(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error("Erro ao carregar documentos:", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchDocs(); }, []);

    const handleDownload = (docId) => {
        window.open(`${API_URL}/documents/download/${docId}`, '_blank');
    };

    const handleDelete = async (docId) => {
        if (!window.confirm("Deseja realmente excluir este documento do repositório?")) return;
        try {
            await axios.delete(`${API_URL}/documents/${docId}`);
            fetchDocs();
        } catch (err) {
            alert("Erro ao excluir documento");
        }
    };

    const handleClearAll = async () => {
        if (!window.confirm("ATENÇÃO: Isso irá limpar todo o histórico de documentos validados. Os arquivos físicos não serão apagados por segurança. Continuar?")) return;
        try {
            await axios.delete(`${API_URL}/documents/clear/all`);
            fetchDocs();
        } catch (err) {
            alert("Erro ao limpar base");
        }
    };

    const filteredDocs = docs.filter(d =>
        (d.filename || "").toLowerCase().includes(filter.toLowerCase()) ||
        (d.cnpj_extracted || "").includes(filter) ||
        (d.competence_extracted || "").includes(filter) ||
        (d.agent_name || "").toLowerCase().includes(filter.toLowerCase()) ||
        (d.ons_code || "").includes(filter)
    );

    return (
        <div style={{ padding: '40px', color: '#E2E8F0', maxWidth: '1400px', margin: '0 auto', fontFamily: 'Inter, sans-serif' }}>

            {/* Header Corporativo */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '40px' }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '2.5rem', fontWeight: '800', letterSpacing: '-0.025em', color: '#F8FAFC' }}>
                        Auditoria de Documentos
                    </h1>
                    <p style={{ color: '#94A3B8', fontSize: '1.1rem', marginTop: '8px' }}>
                        Central de custódia e validação de faturas TUST.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <button
                        onClick={handleClearAll}
                        style={{
                            background: 'transparent',
                            color: '#EF4444',
                            padding: '12px 24px',
                            borderRadius: '10px',
                            display: 'flex',
                            gap: '12px',
                            alignItems: 'center',
                            fontWeight: '600',
                            border: '1px solid #EF4444',
                            cursor: 'pointer',
                        }}
                    >
                        <IconTrash /> Limpar Base
                    </button>
                    <button
                        onClick={fetchDocs}
                        style={{
                            background: '#3B82F6',
                            color: 'white',
                            padding: '12px 24px',
                            borderRadius: '10px',
                            display: 'flex',
                            gap: '12px',
                            alignItems: 'center',
                            fontWeight: '600',
                            border: 'none',
                            cursor: 'pointer',
                        }}
                    >
                        <IconRefresh animate={loading} /> Recarregar
                    </button>
                </div>
            </div>

            {/* Barra de Filtros Minimalista */}
            <div style={{
                marginBottom: '24px',
                background: '#1E293B',
                padding: '16px',
                borderRadius: '12px',
                border: '1px solid #334155',
                display: 'flex',
                gap: '20px',
                alignItems: 'center'
            }}>
                <div style={{ position: 'relative', flex: 1 }}>
                    <input
                        type="text"
                        placeholder="Pesquisar por Base, Agente, ONS, CNPJ ou Competência..."
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                        style={{
                            width: '100%',
                            padding: '12px 16px',
                            background: '#0F172A',
                            border: '1px solid #475569',
                            color: '#F8FAFC',
                            borderRadius: '8px',
                            outline: 'none',
                            fontSize: '0.95rem'
                        }}
                    />
                </div>
                <div style={{ fontSize: '0.9rem', color: '#94A3B8', fontWeight: '500' }}>
                    <span style={{ color: '#3B82F6' }}>{filteredDocs.length}</span> documentos processados
                </div>
            </div>

            {/* Tabela de Dados Auditados */}
            <div style={{
                background: '#1E293B',
                borderRadius: '12px',
                border: '1px solid #334155',
                overflow: 'hidden',
                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
            }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead style={{ background: '#334155', color: '#CBD5E1', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        <tr>
                            <th style={{ padding: '16px 20px' }}>Ref #</th>
                            <th>Base</th>
                            <th>Agente (ONS)</th>
                            <th>Processado em</th>
                            <th>Mês Referência</th>
                            <th>Valor Auditado</th>
                            <th style={{ textAlign: 'center', paddingRight: '20px' }}>Ações</th>
                        </tr>
                    </thead>
                    <tbody style={{ fontSize: '0.95rem' }}>
                        {filteredDocs.map((doc) => (
                            <tr key={doc.id} style={{ borderBottom: '1px solid #334155', transition: 'background 0.2s' }}>
                                <td style={{ padding: '16px 20px', color: '#94A3B8', fontFamily: 'monospace' }}>#{String(doc.id).padStart(4, '0')}</td>
                                <td>
                                    <span style={{
                                        background: doc.base === 'DE' ? '#7C3AED' : '#475569',
                                        color: 'white',
                                        padding: '2px 8px',
                                        borderRadius: '4px',
                                        fontSize: '0.75rem',
                                        fontWeight: '800'
                                    }}>
                                        {doc.base || '---'}
                                    </span>
                                </td>
                                <td>
                                    <div style={{ fontWeight: '600' }}>{doc.agent_name || 'Desconhecido'}</div>
                                    <div style={{ fontSize: '0.75rem', color: '#64748B' }}>ONS: {doc.ons_code || '---'}</div>
                                </td>
                                <td style={{ fontSize: '0.85rem' }}>{doc.created_at ? new Date(doc.created_at).toLocaleString('pt-BR') : '---'}</td>
                                <td>
                                    <span style={{
                                        background: '#1E3A8A',
                                        color: '#BFDBFE',
                                        padding: '4px 10px',
                                        borderRadius: '6px',
                                        fontSize: '0.85rem',
                                        fontWeight: '700'
                                    }}>
                                        {doc.competence_extracted}
                                    </span>
                                </td>
                                <td style={{ fontWeight: '700', color: '#10B981' }}>
                                    {doc.invoice_value ? `R$ ${doc.invoice_value}` : '---'}
                                </td>
                                <td style={{ textAlign: 'center', paddingRight: '20px' }}>
                                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'center' }}>
                                        <button
                                            onClick={() => setSelectedDoc(doc)}
                                            style={{ background: '#475569', color: '#F8FAFC', padding: '8px', borderRadius: '8px', border: 'none', cursor: 'pointer', display: 'flex' }}
                                            title="Ver Detalhes"
                                        >
                                            <IconEye />
                                        </button>
                                        <button
                                            onClick={() => handleDownload(doc.id)}
                                            style={{ background: '#10B981', color: 'white', padding: '8px', borderRadius: '8px', border: 'none', cursor: 'pointer', display: 'flex' }}
                                            title="Download XML"
                                        >
                                            <IconDownload />
                                        </button>
                                        <button
                                            onClick={() => handleDelete(doc.id)}
                                            style={{ background: '#334155', color: '#EF4444', padding: '8px', borderRadius: '8px', border: 'none', cursor: 'pointer', display: 'flex' }}
                                            title="Excluir Registro"
                                        >
                                            <IconTrash size={16} />
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Modal de Auditoria Detalhada */}
            {selectedDoc && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
                    backgroundColor: 'rgba(15, 23, 42, 0.9)', zIndex: 99999,
                    display: 'flex', justifyContent: 'center', alignItems: 'center',
                    backdropFilter: 'blur(4px)'
                }}>
                    <div style={{
                        background: '#1E293B', width: '560px', padding: '40px',
                        borderRadius: '24px', border: '1px solid #475569',
                        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '32px' }}>
                            <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: '800', color: '#F8FAFC' }}>
                                Ficha de Auditoria
                            </h2>
                            <button
                                onClick={() => setSelectedDoc(null)}
                                style={{ background: 'transparent', border: 'none', color: '#94A3B8', fontSize: '1.8rem', cursor: 'pointer' }}
                            >
                                ×
                            </button>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '40px' }}>
                            <div style={{ background: '#0F172A', padding: '16px', borderRadius: '12px', border: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <label style={{ color: '#64748B', fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', marginBottom: '4px', display: 'block' }}>Base / Empresa</label>
                                    <div style={{ color: '#F8FAFC', fontWeight: '700' }}>{selectedDoc.base} - {selectedDoc.agent_name}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <label style={{ color: '#64748B', fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', marginBottom: '4px', display: 'block' }}>Código ONS</label>
                                    <div style={{ color: '#F8FAFC', fontWeight: '700' }}>{selectedDoc.ons_code}</div>
                                </div>
                            </div>

                            <div style={{ background: '#0F172A', padding: '16px', borderRadius: '12px', border: '1px solid #334155' }}>
                                <label style={{ color: '#64748B', fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', marginBottom: '4px', display: 'block' }}>Nome do Arquivo</label>
                                <div style={{ color: '#3B82F6', fontWeight: '700', wordBreak: 'break-all' }}>{selectedDoc.filename}</div>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                                <div style={{ background: '#0F172A', padding: '16px', borderRadius: '12px', border: '1px solid #334155' }}>
                                    <label style={{ color: '#64748B', fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', marginBottom: '4px', display: 'block' }}>Mês Referência</label>
                                    <div style={{ color: '#F8FAFC', fontSize: '1.1rem', fontWeight: '600' }}>{selectedDoc.competence_extracted}</div>
                                </div>
                                <div style={{ background: '#0F172A', padding: '16px', borderRadius: '12px', border: '1px solid #334155' }}>
                                    <label style={{ color: '#64748B', fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', marginBottom: '4px', display: 'block' }}>Data Processo</label>
                                    <div style={{ color: '#F1F5F9' }}>{selectedDoc.created_at ? new Date(selectedDoc.created_at).toLocaleDateString() : '---'}</div>
                                </div>
                            </div>

                            <div style={{ background: '#0F172A', padding: '16px', borderRadius: '12px', border: '1px solid #334155' }}>
                                <label style={{ color: '#64748B', fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', marginBottom: '4px', display: 'block' }}>CNPJ Transmissora (Lido no XML)</label>
                                <div style={{ color: '#F8FAFC', fontSize: '1.2rem', fontFamily: 'monospace', letterSpacing: '0.05em' }}>{selectedDoc.cnpj_extracted}</div>
                            </div>

                            <div style={{ background: '#0F172A', padding: '20px', borderRadius: '12px', border: '1px solid #059669', textAlign: 'center' }}>
                                <label style={{ color: '#10B981', fontSize: '0.75rem', fontWeight: '800', textTransform: 'uppercase', marginBottom: '4px', display: 'block' }}>Valor Identificado no XML</label>
                                <div style={{ color: '#F8FAFC', fontSize: '2rem', fontWeight: '900' }}>R$ {selectedDoc.invoice_value || '0,00'}</div>
                            </div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <button
                                onClick={() => handleDownload(selectedDoc.id)}
                                style={{
                                    background: '#3B82F6', color: 'white', padding: '14px', borderRadius: '12px', border: 'none',
                                    display: 'flex', justifyContent: 'center', gap: '10px', alignItems: 'center', fontWeight: '700',
                                    cursor: 'pointer'
                                }}
                            >
                                <IconFileXml /> Download XML
                            </button>
                            <button
                                onClick={() => handleDelete(selectedDoc.id)}
                                style={{
                                    background: '#EF4444', color: 'white', padding: '14px', borderRadius: '12px', border: 'none',
                                    display: 'flex', justifyContent: 'center', gap: '10px', alignItems: 'center', fontWeight: '700',
                                    cursor: 'pointer'
                                }}
                            >
                                <IconTrash /> Excluir Registro
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                tr:hover { background-color: #334155 !important; }
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                .animate-spin { animation: spin 1s linear infinite; }
            `}</style>
        </div>
    );
};

export default DocumentManager;
