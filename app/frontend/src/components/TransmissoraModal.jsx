import { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = "/api"

function TransmissoraModal({ show, onClose, onLog }) {
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
            if (onLog) onLog(`Planilha processada: ${res.data.message}`)
            fetchTransmissoras()
        } catch (err) {
            alert("Erro no upload: " + (err.response?.data?.detail || err.message))
        } finally {
            setIsUploading(false)
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
        if (show) fetchTransmissoras()
    }, [show])

    if (!show) return null

    return (
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
                        <button onClick={onClose} style={{ background: '#333', border: 'none', borderRadius: '50%', width: '40px', height: '40px', fontSize: '1.2em', cursor: 'pointer' }}>×</button>
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

                    {selectedTransmissoraDetails && (
                        <DetailModal details={selectedTransmissoraDetails} onClose={() => setSelectedTransmissoraDetails(null)} />
                    )}
                </div>
            </div>
        </div>
    )
}

function DetailModal({ details, onClose }) {
    const d = JSON.parse(details.dados_json || "{}");
    const rowStyle = { display: 'flex', gap: '1rem', marginBottom: '8px', fontSize: '12px' };
    const labelStyle = { color: '#000', fontWeight: 'bold', minWidth: '100px' };
    const sectionTitleStyle = { color: '#88ba2a', fontSize: '14px', fontWeight: 'bold', borderBottom: '1px solid #88ba2a', paddingBottom: '2px', marginBottom: '10px', marginTop: '15px' };
    const boxStyle = { border: '1px solid #ccc', padding: '10px', borderRadius: '2px', marginBottom: '10px' };

    return (
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
                            <div style={{ border: '1px solid #88ba2a', padding: '2px 10px', fontWeight: 'bold' }}>{details.codigo_ons}</div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontWeight: 'bold', fontSize: '13px' }}>Sigla</span>
                            <div style={{ border: '1px solid #88ba2a', padding: '2px 10px', color: '#333', fontWeight: 'bold' }}>{details.sigla}</div>
                        </div>
                    </div>
                    <button onClick={onClose} style={{ background: '#e74c3c', border: 'none', color: 'white', padding: '5px 15px', cursor: 'pointer', borderRadius: '4px' }}>FECHAR</button>
                </div>

                {/* Conteúdo Scrollável */}
                <div style={{ padding: '20px', overflowY: 'auto', backgroundColor: '#fff' }}>
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
                            <div style={{ flex: 2 }}><span style={labelStyle}>CNPJ:</span> {details.cnpj}</div>
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
                </div>
            </div>
        </div>
    )
}

export default TransmissoraModal
