# Consulta de Processos com Comunicação Segura (TLS)

Projeto Integrador III-A — Análise e Desenvolvimento de Sistemas (EaD) — PUC Goiás, 2026.

Aplicação **cliente-servidor em linha de comando** que permite ao cliente do escritório parceiro
**Almeida Campos Advogados Associados** (direito médico) **consultar o andamento dos próprios processos**.
Toda a comunicação é **criptografada com TLS**.

> ⚠️ **Protótipo acadêmico.** Todos os nomes, números de processo e informações do `dados.json`
> são **fictícios**. Nenhum dado real de clientes é usado (LGPD — dados de saúde são dados sensíveis).

## Funcionalidades

1. Login do cliente com **código de acesso + senha**.
2. **Meus processos:** lista os processos do cliente (número, tipo de ação, fase, última atualização).
3. **Detalhes de um processo:** órgão julgador, fase, advogado responsável, próximo passo e últimas movimentações.
4. Sair.

## Arquitetura

```
┌──────────────┐   TLS 1.2/1.3 (TCP)    ┌───────────────┐      ┌────────────┐
│  cliente.py  │ ─────────────────────▶ │  servidor.py  │ ───▶ │ dados.json │
│ (menu CLI)   │ ◀───────────────────── │ (multithread) │      └────────────┘
└──────────────┘  mensagens JSON/linha  └───────────────┘
```

- **Servidor:** guarda os dados, recebe as requisições, autentica o cliente, aplica o controle de acesso e responde.
- **Cliente:** mostra o menu, envia as requisições pela rede e exibe as respostas formatadas.
- **Protocolo:** cada mensagem é um objeto JSON em uma linha (`\n` no fim).

| Requisição (cliente → servidor) | Resposta de sucesso |
|---|---|
| `{"acao": "login", "codigo": "...", "senha": "..."}` | `{"status": "ok", "nome": "..."}` |
| `{"acao": "listar_processos"}` | `{"status": "ok", "processos": [...]}` |
| `{"acao": "detalhar_processo", "numero": "..."}` | `{"status": "ok", "processo": {...}}` |
| `{"acao": "sair"}` | `{"status": "ok", "mensagem": "Sessão encerrada."}` |

Em caso de falha: `{"status": "erro", "mensagem": "..."}`.

## Segurança

| Mecanismo | Como foi feito |
|---|---|
| Comunicação criptografada | Módulo `ssl` do Python (TLS, versão mínima 1.2) com certificado X.509 |
| Autenticidade do servidor | O cliente valida o certificado (`cert.pem`) e o nome do host; certificado desconhecido → conexão abortada |
| Senhas | Nunca em texto puro: hash **PBKDF2-HMAC-SHA256** com salt aleatório e 200 mil iterações (`hashlib`) |
| Controle de acesso | Cada cliente só vê os **próprios** processos; tentativas de acessar outros são negadas e registradas em log |
| Força bruta | Máximo de **3 tentativas** de login por conexão |
| Enumeração de usuários | Mesma mensagem e mesmo tempo de resposta para código inexistente ou senha errada |
| Robustez | Limite de 64 KB por mensagem, tempo limite de inatividade, JSON validado |
| Chave privada | `certs/key.pem` fica fora do repositório (`.gitignore`) |

## Requisitos

- **Python 3.8 ou superior** — só a biblioteca padrão, **nada para instalar com pip**.
- **OpenSSL** apenas para gerar o certificado (no Windows, já vem com o **Git for Windows**).

## Como executar

Abra um terminal na pasta do projeto.

**1. Gere o certificado (só na primeira vez):**
```bash
python gerar_certificado.py
```
Cria `certs/cert.pem` (certificado) e `certs/key.pem` (chave privada).

**2. Inicie o servidor (terminal 1):**
```bash
python servidor.py
```

**3. Inicie o cliente (terminal 2):**
```bash
python cliente.py
```

### Usuários de demonstração (fictícios)

| Código | Senha | Processos |
|---|---|---|
| `CLI-1001` | `maria2026` | 2 |
| `CLI-1002` | `joao2026` | 2 |
| `CLI-1003` | `ana2026` | 1 |

Para trocar uma senha: `python cadastrar_senha.py CLI-1001`

> Dica: rode o cliente no **Prompt de Comando / PowerShell / terminal**. Em alguns consoles de IDE
> a digitação da senha (`getpass`) pode aparecer na tela ou travar.

### Usando duas máquinas na mesma rede

```bash
python gerar_certificado.py --ip 192.168.0.10     # IP da máquina do servidor
python servidor.py --host 0.0.0.0
# copie certs/cert.pem (NÃO a key.pem) para a máquina do cliente e rode:
python cliente.py --host 192.168.0.10
```

## Testes automatizados

```bash
python -m unittest discover -s tests -v
```

Os 12 testes cobrem: uso de TLS 1.2/1.3, recusa de conexão sem TLS, rejeição de certificado
não confiável, login válido e inválido, bloqueio após 3 tentativas, consulta sem login,
listagem só dos próprios processos, bloqueio de acesso a processo de outro cliente e ações inválidas.

## Estrutura

```
├── servidor.py           # servidor TLS multithread
├── cliente.py            # cliente com menu em linha de comando
├── comum.py              # protocolo de mensagens e hash de senhas
├── dados.json            # dados FICTÍCIOS (clientes e processos)
├── gerar_certificado.py  # gera certificado autoassinado via OpenSSL
├── cadastrar_senha.py    # define/troca senha de um cliente
├── certs/                # cert.pem e key.pem (não versionados)
└── tests/
    └── test_integracao.py
```
