import axios from 'axios'
const API_URL = "/api"

function EmpresaManager({ empresas, onUpdate, onLog, formData, setFormData, editingId, setEditingId }) {

    const handleInputChange = (e) => {
        const { name, value } = e.target
        setFormData(prev => ({ ...prev, [name]: value }))
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        try {
            if (editingId) {
                await axios.put(`${API_URL}/empresas/${editingId}`, formData)
                onLog(`Empresa atualizada: ${formData.nome_empresa}`)
            } else {
                await axios.post(`${API_URL}/empresas`, formData)
                onLog(`Nova empresa criada: ${formData.nome_empresa}`)
            }
            setFormData({ codigo_ons: '', nome_empresa: '', cnpj: '', base: 'AETE' })
            setEditingId(null)
            onUpdate()
        } catch (err) {
            console.error(err)
            alert("Erro ao salvar empresa")
        }
    }

    const handleEdit = (emp) => {
        setFormData({ codigo_ons: emp.codigo_ons, nome_empresa: emp.nome_empresa, cnpj: emp.cnpj || '', base: emp.base })
        setEditingId(emp.id)
    }

    const handleDelete = async (id) => {
        if (!confirm("Tem certeza que deseja excluir?")) return
        try {
            await axios.delete(`${API_URL}/empresas/${id}`)
            onLog(`Empresa excluída.`)
            onUpdate()
        } catch (err) {
            console.error(err)
        }
    }

    const syncEmpresas = async () => {
        try {
            await axios.post(`${API_URL}/empresas/sync`)
            onUpdate()
            onLog("Banco sincronizado com sucesso!")
        } catch (err) {
            console.error("Erro ao sincronizar", err)
        }
    }

    return (
        <>
            <div className="card" style={{ marginBottom: '1rem' }}>
                <h3>{editingId ? 'Editar Empresa' : 'Adicionar Nova Empresa / Base'}</h3>
                <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <input
                        name="codigo_ons"
                        value={formData.codigo_ons}
                        onChange={handleInputChange}
                        placeholder="Cód. ONS (ex: 4284)"
                        required
                        style={{ padding: '0.5em', borderRadius: '4px', border: '1px solid #444', background: '#222', color: 'white' }}
                    />
                    <input
                        name="nome_empresa"
                        value={formData.nome_empresa}
                        onChange={handleInputChange}
                        placeholder="Nome Empresa"
                        required
                        style={{ flex: 1, padding: '0.5em', borderRadius: '4px', border: '1px solid #444', background: '#222', color: 'white' }}
                    />
                    <input
                        name="cnpj"
                        value={formData.cnpj}
                        onChange={handleInputChange}
                        placeholder="CNPJ (Equatorial)"
                        style={{ width: '150px', padding: '0.5em', borderRadius: '4px', border: '1px solid #444', background: '#222', color: 'white' }}
                    />
                    <input
                        name="base"
                        value={formData.base}
                        onChange={handleInputChange}
                        placeholder="Base (ex: AETE)"
                        required
                        style={{ width: '80px', padding: '0.5em', borderRadius: '4px', border: '1px solid #444', background: '#222', color: 'white' }}
                    />
                    <button type="submit" style={{ padding: '0.5em 1em', fontSize: '0.9em' }}>
                        {editingId ? 'Salvar' : 'Adicionar'}
                    </button>
                    {editingId && (
                        <button type="button" onClick={() => { setEditingId(null); setFormData({ codigo_ons: '', nome_empresa: '', cnpj: '', base: 'AETE' }) }} style={{ background: '#555' }}>
                            Cancelar
                        </button>
                    )}
                </form>
            </div>

            <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3>Empresas Cadastradas</h3>
                    <button
                        onClick={syncEmpresas}
                        style={{ fontSize: '0.8em', padding: '0.5em', background: 'transparent', border: '1px solid #555' }}
                    >
                        🔄 Sincronizar DB
                    </button>
                </div>

                {empresas.length === 0 ? (
                    <p style={{ color: '#666' }}>Nenhuma empresa. Adicione ou sincronize.</p>
                ) : (
                    <table>
                        <thead>
                            <tr>
                                <th>ID ONS</th>
                                <th>Nome Empresa</th>
                                <th>CNPJ</th>
                                <th>Base</th>
                                <th>Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            {empresas.map(emp => (
                                <tr key={emp.id}>
                                    <td>{emp.codigo_ons}</td>
                                    <td>{emp.nome_empresa}</td>
                                    <td style={{ fontSize: '0.85em', color: '#888' }}>{emp.cnpj || '-'}</td>
                                    <td>
                                        <span style={{
                                            background: '#333',
                                            padding: '2px 6px',
                                            borderRadius: '4px',
                                            fontSize: '0.8em',
                                            border: '1px solid #444'
                                        }}>
                                            {emp.base}
                                        </span>
                                    </td>
                                    <td>
                                        <button onClick={() => handleEdit(emp)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 5px', fontSize: '1.2em' }}>✏️</button>
                                        <button onClick={() => handleDelete(emp.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 5px', fontSize: '1.2em' }}>🗑️</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </>
    )
}

export default EmpresaManager
