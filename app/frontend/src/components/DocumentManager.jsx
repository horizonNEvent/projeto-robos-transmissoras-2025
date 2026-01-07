import React, { useState, useEffect } from 'react';
import axios from 'axios';

// SVGs Inline para garantir que funcione sem dependências
const IconSearch = ({ className = '' }) => <svg className={`w-5 h-5 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>;
const IconDownload = ({ className = '' }) => <svg className={`w-5 h-5 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a2 2 0 002 2h12a2 2 0 002-2v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>;
const IconCheck = ({ className = '' }) => <svg className={`w-6 h-6 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>;
const IconBuilding = ({ className = '' }) => <svg className={`w-4 h-4 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-7h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>;
const IconCalendar = ({ className = '' }) => <svg className={`w-4 h-4 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>;
const IconCurrency = ({ className = '' }) => <svg className={`w-4 h-4 ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>;
const IconRefresh = ({ animate, className = '' }) => <svg className={`w-5 h-5 ${animate ? 'animate-spin' : ''} ${className}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>;

const API_URL = "/api";

const DocumentManager = () => {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');

    const fetchDocuments = async () => {
        setLoading(true);
        try {
            const response = await axios.get(`${API_URL}/documents`);
            setDocuments(response.data);
        } catch (error) {
            console.error("Erro ao carregar documentos:", error);
            alert("Erro ao carregar lista de documentos.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDocuments();
    }, []);

    const handleDownload = (docId, filename) => {
        window.open(`${API_URL}/documents/download/${docId}`, '_blank');
    };

    const filteredDocs = documents.filter(doc =>
        doc.filename.toLowerCase().includes(filter.toLowerCase()) ||
        (doc.cnpj_extracted && doc.cnpj_extracted.includes(filter)) ||
        (doc.competence_extracted && doc.competence_extracted.includes(filter))
    );

    return (
        <div className="p-6 text-white bg-slate-900 min-h-screen">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-3xl font-bold flex items-center gap-3 text-blue-400">
                        <IconSearch className="text-4xl" />
                        Documentos Validados
                    </h1>
                    <p className="text-slate-400 mt-2">Repositório de XMLs processados e auditados pelos robôs.</p>
                </div>
                <button
                    onClick={fetchDocuments}
                    className="bg-blue-600 hover:bg-blue-700 p-3 rounded-xl transition-all flex items-center gap-2 shadow-lg shadow-blue-900/20"
                >
                    <IconRefresh animate={loading} />
                    Atualizar
                </button>
            </div>

            {/* Barra de Busca e Filtros */}
            <div className="bg-slate-800/50 p-4 rounded-2xl mb-6 border border-slate-700/50 flex flex-wrap gap-4 items-center">
                <div className="flex-1 min-w-[300px] relative">
                    <input
                        type="text"
                        placeholder="Buscar por arquivo, CNPJ ou competência..."
                        className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 pl-10 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-sm"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                    />
                    <IconSearch className="absolute left-3 top-3.5 text-slate-500" />
                </div>
                <div className="text-sm text-slate-400">
                    Mostrando <span className="text-blue-400 font-bold">{filteredDocs.length}</span> documentos
                </div>
            </div>

            {loading && documents.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-64 text-slate-500">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-4"></div>
                    <p>Carregando repositório...</p>
                </div>
            ) : filteredDocs.length === 0 ? (
                <div className="bg-slate-800/30 border-2 border-dashed border-slate-700 rounded-3xl p-12 text-center">
                    <IconSearch className="text-6xl text-slate-700 mx-auto mb-4" />
                    <h3 className="text-xl font-medium text-slate-400">Nenhum documento encontrado</h3>
                    <p className="text-slate-500 mt-2">Aguarde a conclusão de um robô agendado para ver os arquivos aqui.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredDocs.map((doc) => (
                        <div
                            key={doc.id}
                            className="bg-slate-800 border border-slate-700 rounded-2xl p-5 hover:border-blue-500/50 transition-all group relative overflow-hidden"
                        >
                            <div className="absolute top-0 right-0 p-4">
                                <IconCheck className="text-green-500 opacity-50 group-hover:opacity-100 transition-all" />
                            </div>

                            <div className="flex items-center gap-4 mb-4">
                                <div className="p-3 bg-blue-500/10 rounded-xl">
                                    <IconSearch className="text-blue-400" />
                                </div>
                                <div className="truncate pr-8">
                                    <h4 className="font-bold text-slate-100 truncate text-sm" title={doc.filename}>
                                        {doc.filename}
                                    </h4>
                                    <span className="text-xs text-slate-500">ID: #{doc.id} • {new Date(doc.created_at).toLocaleDateString()}</span>
                                </div>
                            </div>

                            <div className="space-y-3 bg-slate-900/50 p-4 rounded-xl border border-slate-700/50 mb-5">
                                <div className="flex items-center gap-3 text-sm">
                                    <IconBuilding className="text-slate-500" />
                                    <span className="text-slate-300 font-medium">CNPJ:</span>
                                    <span className="text-slate-400 font-mono tracking-tighter">{doc.cnpj_extracted || 'N/A'}</span>
                                </div>
                                <div className="flex items-center gap-3 text-sm">
                                    <IconCalendar className="text-slate-500" />
                                    <span className="text-slate-300 font-medium">Competência:</span>
                                    <span className="text-slate-400">{doc.competence_extracted || 'N/A'}</span>
                                </div>
                                <div className="flex items-center gap-3 text-sm">
                                    <IconCurrency className="text-slate-500" />
                                    <span className="text-slate-300 font-medium">Valor:</span>
                                    <span className="text-blue-400 font-bold">
                                        {doc.invoice_value ? `R$ ${doc.invoice_value.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}` : 'N/A'}
                                    </span>
                                </div>
                            </div>

                            <button
                                onClick={() => handleDownload(doc.id, doc.filename)}
                                className="w-full bg-slate-700 hover:bg-blue-600 p-3 rounded-xl transition-all flex items-center justify-center gap-2 font-medium"
                            >
                                <IconDownload />
                                Baixar XML
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default DocumentManager;
