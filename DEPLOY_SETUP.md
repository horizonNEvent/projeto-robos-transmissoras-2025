# 🚀 Pipeline de Deploy - GitHub Actions

## Setup Rápido

A pipeline está configurada para fazer deploy automático quando você faz `push` no branch `feature/robot-ui-final`.

### Passo 1: Configurar SSH Key

No seu PC (Bruno), a chave já existe em `C:\Users\Bruno\.ssh\id_ed25519`.

**Copie a chave privada:**
```powershell
Get-Content C:\Users\Bruno\.ssh\id_ed25519
```

### Passo 2: Adicionar Secrets no GitHub

Acesse: https://github.com/horizonNEvent/projeto-robos-transmissoras-2025/settings/secrets/actions

Clique em "New repository secret" e adicione 3 secrets:

#### Secret 1: `SERVER_HOST`
- **Value:** `192.168.0.105`

#### Secret 2: `SERVER_USER`
- **Value:** `dibu7`

#### Secret 3: `SSH_PRIVATE_KEY`
- **Value:** (cole todo o conteúdo do arquivo `id_ed25519` que você copiou acima)
- ⚠️ **IMPORTANTE:** Inclua `-----BEGIN OPENSSH PRIVATE KEY-----` e `-----END OPENSSH PRIVATE KEY-----`

### Passo 3: Testar

Faça um commit simples no branch `feature/robot-ui-final`:
```bash
git add DEPLOY_SETUP.md
git commit -m "docs: pipeline de deploy configurada"
git push origin feature/robot-ui-final
```

Vá para: https://github.com/horizonNEvent/projeto-robos-transmissoras-2025/actions

Você verá o workflow "Deploy to Production" rodando. 🎯

## 📊 O que acontece quando faz push?

1. **GitHub Actions detecta** o push no `feature/robot-ui-final`
2. **SSH se conecta** ao servidor `192.168.0.105` como `dibu7`
3. **Git pull** faz download das atualizações
4. **deploy.ps1 roda:**
   - Para os containers antigos
   - Reconstrói as imagens Docker
   - Sobe novos containers
   - Limpa imagens órfãs
5. **App fica online** em:
   - Backend: http://192.168.0.105:8000
   - Frontend: http://192.168.0.105:5173

## 🔧 Troubleshooting

### Erro: "permission denied"
- Verifique se a chave SSH foi adicionada corretamente no GitHub
- Confirme que em `C:\ProgramData\ssh\administrators_authorized_keys` tem a chave pública

### Erro: "docker not found"
- O Docker Desktop precisa estar rodando no servidor
- Ou Docker tá com problema de credenciais (veja abaixo)

### Erro: "image pull failed"
Se Docker não conseguir puxar imagens do Docker Hub:
```powershell
# No servidor, faça login manualmente:
docker login
# Digite seu user/pass do Docker Hub
```

## 📝 Arquivos importantes

- `.github/workflows/deploy.yml` - O workflow do GitHub Actions
- `deploy.ps1` - Script que roda no servidor (PowerShell)
- Este arquivo - Documentação

## 🔐 Segurança

- A chave SSH é privada e só você (e GitHub) têm
- A chave fica criptografada nos secrets do GitHub
- Ninguém consegue ver a chave depois de salva (nem você!)

## 📞 Próximas Melhorias

- [ ] Adicionar testes automatizados antes do deploy
- [ ] Notifications no Slack/Discord quando deploy falha
- [ ] Rollback automático se algo der errado
- [ ] Deploy em staging antes de produção

---

Pronto! Pipeline configurada. Agora é só dar `git push` e o deploy sai automático! 🚀
