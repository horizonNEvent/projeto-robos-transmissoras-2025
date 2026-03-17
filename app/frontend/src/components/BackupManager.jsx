import { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = '/api/backup';

export default function BackupManager({ onLog }) {
    const [backups, setBackups] = useState([]);
    const [loading, setLoading] = useState(false);
    const [creating, setCreating] = useState(false);

    const fetchBackups = async () => {
        try {
            setLoading(true);
            const res = await axios.get(`${API_URL}/list`);
            setBackups(res.data);
        } catch (err) {
            console.error("Erro ao listar backups:", err);
            onLog && onLog("Erro ao carregar lista de backups.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchBackups();
    }, []);

    const handleCreateBackup = async () => {
        try {
            setCreating(true);
            const res = await axios.post(`${API_URL}/create`);
            onLog && onLog(`✅ Backup criado: ${res.data.filename}`);
            fetchBackups();
        } catch (err) {
            console.error("Erro ao criar backup:", err);
            onLog && onLog("❌ Erro ao criar backup.");
        } finally {
            setCreating(false);
        }
    };

    const handleDownload = (filename) => {
        window.open(`${API_URL}/download/${filename}`, '_blank');
    };

    const handleDelete = async (filename) => {
        if (!window.confirm(`Tem certeza que deseja excluir o backup ${filename}?`)) return;
        try {
            await axios.delete(`${API_URL}/${filename}`);
            onLog && onLog(`🗑️ Backup removido: ${filename}`);
            fetchBackups();
        } catch (err) {
            console.error("Erro ao excluir backup:", err);
            onLog && onLog("❌ Erro ao excluir backup.");
        }
    };

    return (
        <div className="card" style={{ marginTop: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <div>
                    <h3 style={{ margin: 0 }}>💾 Backups do Banco de Dados</h3>
                    <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '0.85rem' }}>
                        Gerencie cópias de segurança do arquivo sql_app.db
                    </p>
                </div>
                <button 
                    onClick={handleCreateBackup} 
                    disabled={creating}
                    style={{ 
                        background: '#0ea5e9', 
                        border: 'none', 
                        color: 'white', 
                        padding: '0.6rem 1.2rem', 
                        borderRadius: '8px', 
                        cursor: 'pointer',
                        fontWeight: 'bold',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                    }}
                >
                    {creating ? '⏳ Gerando...' : '✨ Criar Backup Agora'}
                </button>
            </div>

            <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid #1e293b', borderRadius: '8px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                    <thead style={{ position: 'sticky', top: 0, background: '#1e293b', zIndex: 1 }}>
                        <tr>
                            <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #334155' }}>Arquivo</th>
                            <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #334155' }}>Data</th>
                            <th style={{ textAlign: 'left', padding: '0.75rem', borderBottom: '1px solid #334155' }}>Tamanho</th>
                            <th style={{ textAlign: 'center', padding: '0.75rem', borderBottom: '1px solid #334155' }}>Ações</th>
                        </tr>
                    </thead>
                    <tbody>
                        {backups.length === 0 ? (
                            <tr>
                                <td colSpan="4" style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                                    Nenhum backup encontrado. Clique no botão acima para gerar o primeiro.
                                </td>
                            </tr>
                        ) : (
                            backups.map((b) => (
                                <tr key={b.filename} style={{ borderBottom: '1px solid #0f172a' }}>
                                    <td style={{ padding: '0.75rem', fontFamily: 'monospace' }}>{b.filename}</td>
                                    <td style={{ padding: '0.75rem' }}>{b.created_at}</td>
                                    <td style={{ padding: '0.75rem' }}>{(b.size / 1024 / 1024).toFixed(2)} MB</td>
                                    <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                        <button 
                                            onClick={() => handleDownload(b.filename)}
                                            style={{ background: 'transparent', border: 'none', cursor: 'pointer', marginRight: '8px', title: 'Baixar' }}
                                        >
                                            📥
                                        </button>
                                        <button 
                                            onClick={() => handleDelete(b.filename)}
                                            style={{ background: 'transparent', border: 'none', cursor: 'pointer', title: 'Excluir' }}
                                        >
                                            🗑️
                                        </button>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
            {loading && <p style={{ textAlign: 'center', color: '#64748b', fontSize: '0.8rem', marginTop: '1rem' }}>Atualizando lista...</p>}
        </div>
    );
}
