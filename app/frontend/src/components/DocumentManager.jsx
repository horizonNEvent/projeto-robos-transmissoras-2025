import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
    HiOutlineDocumentSearch,
    HiOutlineDownload,
    HiOutlineCheckCircle,
    HiOutlineOfficeBuilding,
    HiOutlineCalendar,
    HiOutlineCurrencyDollar,
    HiOutlineRefresh
} from 'react-icons/hi';

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
                        <HiOutlineDocumentSearch className="text-4xl" />
                        Documentos Validados
                    </h1>
                    <p className="text-slate-400 mt-2">Repositório de XMLs processados e auditados pelos robôs.</p>
                </div>
                <button
                    onClick={fetchDocuments}
                    className="bg-blue-600 hover:bg-blue-700 p-3 rounded-xl transition-all flex items-center gap-2 shadow-lg shadow-blue-900/20"
                >
                    <HiOutlineRefresh className={loading ? 'animate-spin' : ''} />
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
                    <HiOutlineDocumentSearch className="absolute left-3 top-3.5 text-slate-500 text-lg" />
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
                    <HiOutlineDocumentSearch className="text-6xl text-slate-700 mx-auto mb-4" />
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
                                <HiOutlineCheckCircle className="text-green-500 text-2xl opacity-50 group-hover:opacity-100 transition-all" />
                            </div>

                            <div className="flex items-center gap-4 mb-4">
                                <div className="p-3 bg-blue-500/10 rounded-xl">
                                    <HiOutlineDocumentSearch className="text-2xl text-blue-400" />
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
                                    <HiOutlineOfficeBuilding className="text-slate-500" />
                                    <span className="text-slate-300 font-medium">CNPJ:</span>
                                    <span className="text-slate-400 font-mono tracking-tighter">{doc.cnpj_extracted || 'N/A'}</span>
                                </div>
                                <div className="flex items-center gap-3 text-sm">
                                    <HiOutlineCalendar className="text-slate-500" />
                                    <span className="text-slate-300 font-medium">Competência:</span>
                                    <span className="text-slate-400">{doc.competence_extracted || 'N/A'}</span>
                                </div>
                                <div className="flex items-center gap-3 text-sm">
                                    <HiOutlineCurrencyDollar className="text-slate-500" />
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
                                <HiOutlineDownload />
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
