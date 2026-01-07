import { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = "/api"

export default function ScheduleModal({ show, onClose, configId, label }) {
    const [schedules, setSchedules] = useState([])
    const [loading, setLoading] = useState(false)
    const [newSchedule, setNewSchedule] = useState({
        schedule_time: "08:00",
        days_of_week: "MON,TUE,WED,THU,FRI,SAT,SUN",
        target_competence: "CURRENT",
        active: true
    })

    useEffect(() => {
        if (show && configId) {
            fetchSchedules()
        }
    }, [show, configId])

    const fetchSchedules = async () => {
        setLoading(true)
        try {
            const res = await axios.get(`${API_URL}/config/robots/schedules/${configId}`)
            setSchedules(res.data)
        } catch (err) {
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const handleSave = async (s) => {
        try {
            await axios.post(`${API_URL}/config/robots/schedules`, {
                ...s,
                robot_config_id: configId
            })
            fetchSchedules()
            alert("Agendamento salvo!")
        } catch (err) {
            alert("Erro ao salvar: " + err.message)
        }
    }

    const handleDelete = async (id) => {
        if (!confirm("Remover este agendamento?")) return
        try {
            await axios.delete(`${API_URL}/config/robots/schedules/${id}`)
            fetchSchedules()
        } catch (err) {
            alert(err.message)
        }
    }

    if (!show) return null

    const modalStyle = {
        position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
        backgroundColor: 'rgba(0,0,0,0.8)', zIndex: 10001,
        display: 'flex', justifyContent: 'center', alignItems: 'center'
    }

    return (
        <div style={modalStyle}>
            <div className="card" style={{ width: '500px', maxWidth: '95%', background: '#1a1a1a', padding: '2rem', border: '1px solid #444' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
                    <h2 style={{ margin: 0 }}>📅 Agendar: {label}</h2>
                    <button onClick={onClose} style={{ background: '#333' }}>×</button>
                </div>

                <div style={{ marginBottom: '1.5rem', background: '#222', padding: '1rem', borderRadius: '8px' }}>
                    <h4 style={{ marginTop: 0 }}>➕ Novo Agendamento Todo Dia</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '1rem' }}>
                        <div>
                            <label style={{ fontSize: '0.8rem', color: '#888' }}>Horário</label>
                            <input
                                type="time"
                                value={newSchedule.schedule_time}
                                onChange={e => setNewSchedule({ ...newSchedule, schedule_time: e.target.value })}
                                style={{ width: '100%', padding: '8px', background: '#111', border: '1px solid #444', color: '#fff' }}
                            />
                        </div>
                        <div>
                            <label style={{ fontSize: '0.8rem', color: '#888' }}>Competência Alvo</label>
                            <select
                                value={newSchedule.target_competence}
                                onChange={e => setNewSchedule({ ...newSchedule, target_competence: e.target.value })}
                                style={{ width: '100%', padding: '8px', background: '#111', border: '1px solid #444', color: '#fff' }}
                            >
                                <option value="CURRENT">Mês Atual</option>
                                <option value="NEXT">Próximo Mês</option>
                            </select>
                        </div>
                    </div>
                    <button onClick={() => handleSave(newSchedule)} style={{ width: '100%', background: '#2980b9' }}>Ativar Agendamento Diário</button>
                </div>

                <h4>Agendamentos Ativos</h4>
                <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                    {loading ? <p>Carregando...</p> : (
                        schedules.map(s => (
                            <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px', borderBottom: '1px solid #333' }}>
                                <div>
                                    <strong>{s.schedule_time}</strong>
                                    <span style={{ fontSize: '0.7rem', marginLeft: '10px', background: '#444', padding: '2px 5px', borderRadius: '4px' }}>
                                        Competência: {s.target_competence === 'CURRENT' ? 'Mês Atual' : s.target_competence}
                                    </span>
                                </div>
                                <button onClick={() => handleDelete(s.id)} style={{ background: '#c0392b', padding: '4px 8px', fontSize: '0.7rem' }}>Excluir</button>
                            </div>
                        ))
                    )}
                    {!loading && schedules.length === 0 && <p style={{ color: '#666', fontSize: '0.9rem' }}>Nenhum horário agendado.</p>}
                </div>
            </div>
        </div>
    )
}
