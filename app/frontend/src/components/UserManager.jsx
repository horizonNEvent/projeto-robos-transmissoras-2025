import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = "http://localhost:8000";

function UserManager({ onLog }) {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [editingUser, setEditingUser] = useState(null); // Se null, modo create
    const [formData, setFormData] = useState({ username: '', password: '', email: '', is_active: true });

    const fetchUsers = async () => {
        try {
            setLoading(true);
            const res = await axios.get(`${API_URL}/auth/users`);
            setUsers(res.data);
        } catch (error) {
            onLog(`Erro ao buscar usuários: ${error.message}`);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (editingUser) {
                // Edit mode (PUT)
                await axios.put(`${API_URL}/auth/users/${editingUser.id}`, {
                    email: formData.email,
                    password: formData.password, // Pode ser vazio
                    is_active: formData.is_active
                });
                onLog(`Usuário ${editingUser.username} atualizado.`);
            } else {
                // Create mode (POST)
                if (!formData.username || !formData.password) {
                    alert("Nome e Senha são obrigatórios para criar!");
                    return;
                }
                await axios.post(`${API_URL}/auth/register`, {
                    username: formData.username,
                    password: formData.password,
                    email: formData.email
                });
                onLog(`Novo usuário ${formData.username} criado.`);
            }
            resetForm();
            fetchUsers();
        } catch (error) {
            onLog(`Erro ao salvar usuário: ${error.response?.data?.detail || error.message}`);
            alert(`Erro: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("Certeza que deseja remover este usuário?")) return;
        try {
            await axios.delete(`${API_URL}/auth/users/${id}`);
            onLog("Usuário removido.");
            fetchUsers();
        } catch (error) {
            onLog(`Erro ao deletar: ${error.message}`);
            alert(`Erro: ${error.response?.data?.detail || error.message}`);
        }
    };

    const startEdit = (user) => {
        setEditingUser(user);
        setFormData({
            username: user.username,
            password: '', // Senha vazia no edit significa "não alterar"
            email: user.email || '',
            is_active: user.is_active
        });
    };

    const resetForm = () => {
        setEditingUser(null);
        setFormData({ username: '', password: '', email: '', is_active: true });
    };

    const handleResendEmail = async (id) => {
        try {
            await axios.post(`${API_URL}/auth/resend-confirmation/${id}`);
            onLog("📧 Email de confirmação reenviado!");
            alert("Email de confirmação reenviado com sucesso.");
        } catch (error) {
            onLog(`Erro ao reenviar email: ${error.message}`);
            alert(`Erro: ${error.response?.data?.detail || error.message}`);
        }
    };

    return (
        <div className="card">
            <h3 style={{ borderBottom: '1px solid #334155', paddingBottom: '1rem', marginBottom: '1rem' }}>
                Gerenciamento de Usuários
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '2rem' }}>

                {/* FORM */}
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '12px' }}>
                    <h4 style={{ marginTop: 0 }}>
                        {editingUser ? `Editar: ${editingUser.username}` : 'Cadastrar Novo Usuário'}
                    </h4>

                    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        {!editingUser && (
                            <div>
                                <label style={{ display: 'block', marginBottom: '4px', fontSize: '0.8rem' }}>Usuário *</label>
                                <input
                                    value={formData.username}
                                    onChange={e => setFormData({ ...formData, username: e.target.value })}
                                    placeholder="Login"
                                    required
                                    style={{ width: '100%' }}
                                />
                            </div>
                        )}

                        <div>
                            <label style={{ display: 'block', marginBottom: '4px', fontSize: '0.8rem' }}>
                                {editingUser ? 'Nova Senha (deixe em branco para manter)' : 'Senha *'}
                            </label>
                            <input
                                value={formData.password}
                                onChange={e => setFormData({ ...formData, password: e.target.value })}
                                type="password"
                                placeholder="****"
                                style={{ width: '100%' }}
                            />
                        </div>

                        <div>
                            <label style={{ display: 'block', marginBottom: '4px', fontSize: '0.8rem' }}>E-mail</label>
                            <input
                                value={formData.email}
                                onChange={e => setFormData({ ...formData, email: e.target.value })}
                                placeholder="exemplo@email.com"
                                style={{ width: '100%' }}
                            />
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <input
                                type="checkbox"
                                checked={formData.is_active}
                                onChange={e => setFormData({ ...formData, is_active: e.target.checked })}
                                style={{ width: 'auto' }}
                            />
                            <label>Ativo</label>
                        </div>

                        <div style={{ display: 'flex', gap: '10px' }}>
                            <button type="submit" style={{ flex: 1, background: '#3b82f6' }}>
                                {editingUser ? '💾 Salvar Alterações' : '✨ Criar'}
                            </button>
                            {editingUser && (
                                <button type="button" onClick={resetForm} style={{ background: '#64748b' }}>
                                    Cancelar
                                </button>
                            )}
                        </div>
                    </form>
                </div>

                {/* LIST */}
                <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
                    <table style={{ width: '100%', fontSize: '0.9rem' }}>
                        <thead>
                            <tr style={{ background: 'rgba(255,255,255,0.05)' }}>
                                <th style={{ padding: '8px' }}>User</th>
                                <th style={{ padding: '8px' }}>Email</th>
                                <th style={{ padding: '8px' }}>Status</th>
                                <th style={{ padding: '8px' }}>Verificado</th>
                                <th style={{ padding: '8px', textAlign: 'right' }}>Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            {users.map(u => (
                                <tr key={u.id} style={{ borderBottom: '1px solid #334155' }}>
                                    <td style={{ padding: '8px', fontWeight: 'bold' }}>{u.username}</td>
                                    <td style={{ padding: '8px', color: '#cbd5e1' }}>{u.email || '-'}</td>
                                    <td style={{ padding: '8px' }}>
                                        <span style={{
                                            padding: '2px 8px', borderRadius: '12px', fontSize: '0.7rem',
                                            background: u.is_active ? '#10b981' : '#ef4444', color: 'white'
                                        }}>
                                            {u.is_active ? 'ATIVO' : 'INATIVO'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '8px' }}>
                                        {u.email ? (
                                            <span style={{ color: u.is_verified ? '#10b981' : '#f59e0b', fontSize: '1.2rem' }}>
                                                {u.is_verified ? '✅' : '⏳'}
                                            </span>
                                        ) : '-'}
                                    </td>
                                    <td style={{ padding: '8px', whiteSpace: 'nowrap', textAlign: 'right' }}>
                                        {u.email && !u.is_verified && (
                                            <button
                                                onClick={() => handleResendEmail(u.id)}
                                                title="Reenviar Email de Confirmação"
                                                style={{ padding: '4px 8px', fontSize: '0.8rem', marginRight: '4px', display: 'inline-block', background: '#3b82f6' }}
                                            >
                                                ✉️
                                            </button>
                                        )}
                                        <button
                                            onClick={() => startEdit(u)}
                                            style={{ padding: '4px 8px', fontSize: '0.8rem', marginRight: '4px', display: 'inline-block', background: '#f59e0b' }}
                                        >
                                            ✏️
                                        </button>
                                        <button
                                            onClick={() => handleDelete(u.id)}
                                            style={{ padding: '4px 8px', fontSize: '0.8rem', display: 'inline-block', background: '#ef4444' }}
                                        >
                                            🗑️
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {users.length === 0 && !loading && (
                                <tr>
                                    <td colSpan="4" style={{ textAlign: 'center', padding: '1rem' }}>Nenhum usuário encontrado.</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

export default UserManager;
