import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = "/api";

// Ícones SVG
const IconChevronDown = ({ size = 20, rotated }) => (
    <svg
        width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        style={{ transition: 'transform 0.2s', transform: rotated ? 'rotate(180deg)' : 'rotate(0deg)' }}
    >
        <polyline points="6 9 12 15 18 9" />
    </svg>
);
const IconEye = ({ size = 18 }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
const IconDownload = ({ size = 18 }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
const IconRefresh = ({ animate, size = 18 }) => <svg width={size} height={size} className={animate ? 'animate-spin' : ''} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></svg>
const IconFileXml = ({ size = 18 }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><path d="M8 13h1" /><path d="M8 17h1" /><path d="M12 13h4" /><path d="M12 17h4" /></svg>
const IconTrash = ({ size = 18 }) => <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" /></svg>

const DocumentManager = () => {
    const [docs, setDocs] = useState([]);
    const [loading, setLoading] = useState(false);

    // Filtros
    const [filtroEmpresa, setFiltroEmpresa] = useState("");
    const [filtroCompetencia, setFiltroCompetencia] = useState("");

    // Estado de Expansão (IDs únicos dos grupos)
    const [expanded, setExpanded] = useState({});

    const [selectedDoc, setSelectedDoc] = useState(null);

    const toggleExpand = (id) => {
        setExpanded(prev => ({ ...prev, [id]: !prev[id] }));
    }

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

    // Lógica de Filtragem
    const filteredDocs = docs.filter(d => {
        const matchEmpresa = filtroEmpresa === "" ||
            (d.base || "").toLowerCase().includes(filtroEmpresa.toLowerCase()) ||
            (d.agent_name || "").toLowerCase().includes(filtroEmpresa.toLowerCase()) ||
            (d.ons_code || "").includes(filtroEmpresa);

        const matchCompetencia = filtroCompetencia === "" ||
            (d.competence_extracted || "").includes(filtroCompetencia);

        return matchEmpresa && matchCompetencia;
    });

    // Lógica de Agrupamento Hierárquico
    // Estrutura: { [Base]: { [OnsCode]: { name: "AgentName", competencias: { [Comp]: [docs...] } } } }
    const groupedData = filteredDocs.reduce((acc, doc) => {
        const base = doc.base || "OUTROS";
        const ons = doc.ons_code || "N/A";
        const comp = doc.competence_extracted || "N/A";

        if (!acc[base]) acc[base] = {};
        if (!acc[base][ons]) acc[base][ons] = { name: doc.agent_name || "Desconhecido", competencias: {} };
        if (!acc[base][ons].competencias[comp]) acc[base][ons].competencias[comp] = [];

        acc[base][ons].competencias[comp].push(doc);
        return acc;
    }, {});

    return (
        <div style={{ padding: '40px', color: '#E2E8F0', maxWidth: '1400px', margin: '0 auto', fontFamily: 'Inter, sans-serif' }}>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '30px' }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '2.5rem', fontWeight: '800', letterSpacing: '-0.025em', color: '#F8FAFC' }}>
                        Agentes Vinculados
                    </h1>
                    <p style={{ color: '#94A3B8', fontSize: '1.1rem', marginTop: '8px' }}>
                        Gestão hierárquica por Base, Agente e Competência.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <button onClick={handleClearAll} style={btnStyle('#EF4444', true)}>
                        <IconTrash /> Limpar Base
                    </button>
                    <button onClick={fetchDocs} style={btnStyle('#3B82F6')}>
                        <IconRefresh animate={loading} /> Recarregar
                    </button>
                </div>
            </div>

            {/* Painel de Filtros */}
            <div style={{
                display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px',
                background: '#1E293B', padding: '20px', borderRadius: '16px', border: '1px solid #334155', marginBottom: '30px'
            }}>
                <div>
                    <label style={labelStyle}>Filtrar por Empresa / ONS / Base</label>
                    <input
                        style={inputStyle}
                        placeholder="Ex: Diamante, 3748, DE..."
                        value={filtroEmpresa}
                        onChange={e => setFiltroEmpresa(e.target.value)}
                    />
                </div>
                <div>
                    <label style={labelStyle}>Filtrar por Competência</label>
                    <input
                        style={inputStyle}
                        placeholder="Ex: 2025-12"
                        value={filtroCompetencia}
                        onChange={e => setFiltroCompetencia(e.target.value)}
                    />
                </div>
            </div>

            {/* Lista Hierárquica */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {Object.keys(groupedData).length === 0 && (
                    <div style={{ textAlign: 'center', padding: '40px', color: '#64748B' }}>Nenhum documento encontrado.</div>
                )}

                {/* NÍVEL 1: BASE (ex: DE) */}
                {Object.keys(groupedData).sort().map(baseKey => {
                    const baseGroup = groupedData[baseKey];
                    const baseId = `base-${baseKey}`;
                    const isBaseExpanded = expanded[baseId];

                    return (
                        <div key={baseId} style={{ border: '1px solid #334155', borderRadius: '12px', overflow: 'hidden', background: '#0F172A' }}>
                            <div
                                onClick={() => toggleExpand(baseId)}
                                style={{
                                    padding: '16px 20px', background: '#1E293B', cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', gap: '12px',
                                    borderBottom: isBaseExpanded ? '1px solid #334155' : 'none'
                                }}
                            >
                                <IconChevronDown rotated={isBaseExpanded} />
                                <span style={{
                                    background: '#7C3AED', color: 'white', padding: '4px 8px', borderRadius: '6px', fontSize: '0.85rem', fontWeight: '800'
                                }}>
                                    {baseKey}
                                </span>
                                <span style={{ fontWeight: '600', color: '#CBD5E1' }}>Base de Processamento</span>
                            </div>

                            {isBaseExpanded && (
                                <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>

                                    {/* NÍVEL 2: AGENTE ONS (ex: 3748) */}
                                    {Object.keys(baseGroup).sort().map(onsKey => {
                                        const onsData = baseGroup[onsKey];
                                        const onsId = `${baseId}-ons-${onsKey}`;
                                        const isOnsExpanded = expanded[onsId];

                                        return (
                                            <div key={onsId} style={{ border: '1px solid #334155', borderRadius: '8px', background: '#1E293B' }}>
                                                <div
                                                    onClick={() => toggleExpand(onsId)}
                                                    style={{
                                                        padding: '12px 20px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                                        borderBottom: isOnsExpanded ? '1px solid #334155' : 'none'
                                                    }}
                                                >
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                                        <IconChevronDown rotated={isOnsExpanded} size={16} />
                                                        <span style={{ fontWeight: '700', color: '#F8FAFC', fontSize: '1.1rem' }}>{onsKey} - {onsData.name}</span>
                                                    </div>
                                                </div>

                                                {isOnsExpanded && (
                                                    <div style={{ padding: '10px', background: '#020617' }}>

                                                        {/* NÍVEL 3: COMPETÊNCIA (ex: 2025-12) */}
                                                        {Object.keys(onsData.competencias).sort().reverse().map(compKey => {
                                                            const docsList = onsData.competencias[compKey];
                                                            const compId = `${onsId}-comp-${compKey}`;
                                                            const isCompExpanded = expanded[compId];

                                                            return (
                                                                <div key={compId} style={{ marginBottom: '8px' }}>
                                                                    <div
                                                                        onClick={() => toggleExpand(compId)}
                                                                        style={{
                                                                            padding: '10px 16px', borderRadius: '6px', background: '#1E293B',
                                                                            border: '1px solid #334155', cursor: 'pointer',
                                                                            display: 'flex', alignItems: 'center', gap: '10px'
                                                                        }}
                                                                    >
                                                                        <IconChevronDown rotated={isCompExpanded} size={16} />
                                                                        <span style={{
                                                                            background: '#0EA5E9', color: 'white', fontWeight: '700', fontSize: '0.8rem', padding: '2px 8px', borderRadius: '4px'
                                                                        }}>
                                                                            {compKey}
                                                                        </span>
                                                                        <span style={{ color: '#94A3B8', fontSize: '0.85rem' }}>{docsList.length} documentos</span>
                                                                    </div>

                                                                    {/* TABELA FINAL DE DOCUMENTOS */}
                                                                    {isCompExpanded && (
                                                                        <div style={{ marginTop: '8px', marginLeft: '24px' }}>
                                                                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                                                                                <thead>
                                                                                    <tr style={{ color: '#64748B', borderBottom: '1px solid #334155', textAlign: 'left' }}>
                                                                                        <th style={{ padding: '8px' }}>Arquivo</th>
                                                                                        <th>Processado em</th>
                                                                                        <th>Valor</th>
                                                                                        <th style={{ textAlign: 'center' }}>Ações</th>
                                                                                    </tr>
                                                                                </thead>
                                                                                <tbody>
                                                                                    {docsList.map(doc => (
                                                                                        <tr key={doc.id} style={{ borderBottom: '1px solid #1E293B' }}>
                                                                                            <td style={{ padding: '12px 8px', color: '#F8FAFC' }}>{doc.filename}</td>
                                                                                            <td style={{ color: '#94A3B8' }}>{new Date(doc.created_at).toLocaleString('pt-BR')}</td>
                                                                                            <td style={{ color: '#10B981', fontWeight: '600' }}>R$ {doc.invoice_value}</td>
                                                                                            <td style={{ textAlign: 'center' }}>
                                                                                                <div style={{ display: 'flex', gap: '8px', justifyContent: 'center' }}>
                                                                                                    <SmallBtn icon={<IconEye />} onClick={() => setSelectedDoc(doc)} color="#475569" />
                                                                                                    <SmallBtn icon={<IconDownload />} onClick={() => handleDownload(doc.id)} color="#10B981" />
                                                                                                    <SmallBtn icon={<IconTrash />} onClick={() => handleDelete(doc.id)} color="#EF4444" />
                                                                                                </div>
                                                                                            </td>
                                                                                        </tr>
                                                                                    ))}
                                                                                </tbody>
                                                                            </table>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>

            {/* Modal Detalhes (Mantido igual) */}
            {selectedDoc && (
                <div style={modalOverlayStyle}>
                    <div style={modalContentStyle}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                            <h2 style={{ margin: 0, color: '#F8FAFC' }}>Detalhes do Documento</h2>
                            <button onClick={() => setSelectedDoc(null)} style={{ background: 'none', border: 'none', color: 'white', fontSize: '1.5rem', cursor: 'pointer' }}>×</button>
                        </div>
                        <div style={{ display: 'grid', gap: '16px' }}>
                            <Field label="Arquivo" value={selectedDoc.filename} />
                            <div style={{ display: 'flex', gap: '20px' }}>
                                <Field label="Base" value={selectedDoc.base} />
                                <Field label="ONS Code" value={selectedDoc.ons_code} />
                            </div>
                            <Field label="Agente" value={selectedDoc.agent_name} />
                            <Field label="CNPJ Extraído" value={selectedDoc.cnpj_extracted} />
                            <Field label="Competência" value={selectedDoc.competence_extracted} />
                            <Field label="Valor" value={`R$ ${selectedDoc.invoice_value}`} highlight />
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                .animate-spin { animation: spin 1s linear infinite; }
                @keyframes spin { 100% { transform: rotate(360deg); } }
            `}</style>
        </div>
    );
};

// Styles Helpers
const btnStyle = (bg, outline) => ({
    background: outline ? 'transparent' : bg,
    color: outline ? bg : 'white',
    border: outline ? `1px solid ${bg}` : 'none',
    padding: '10px 20px', borderRadius: '8px', cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '600'
});

const labelStyle = { display: 'block', color: '#94A3B8', fontSize: '0.85rem', fontWeight: '700', marginBottom: '8px', textTransform: 'uppercase' };
const inputStyle = { width: '100%', padding: '12px', background: '#0F172A', border: '1px solid #475569', borderRadius: '8px', color: 'white', outline: 'none' };

const SmallBtn = ({ icon, onClick, color }) => (
    <button onClick={onClick} style={{ background: color, color: 'white', border: 'none', padding: '6px', borderRadius: '6px', cursor: 'pointer', display: 'flex' }}>
        {icon}
    </button>
);

const Field = ({ label, value, highlight }) => (
    <div style={{ background: '#0F172A', padding: '12px', borderRadius: '8px', border: highlight ? '1px solid #10B981' : '1px solid #334155' }}>
        <label style={{ color: highlight ? '#10B981' : '#64748B', fontSize: '0.75rem', fontWeight: 'bold' }}>{label}</label>
        <div style={{ color: highlight ? '#10B981' : 'white', fontWeight: '600', fontSize: highlight ? '1.2rem' : '1rem' }}>{value || '---'}</div>
    </div>
);

const modalOverlayStyle = {
    position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
    background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(5px)'
};
const modalContentStyle = {
    background: '#1E293B', padding: '30px', borderRadius: '20px', width: '500px', border: '1px solid #475569'
};

export default DocumentManager;
