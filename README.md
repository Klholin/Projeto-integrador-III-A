# Consulta de Processos com Comunicação Segura (TLS)

Projeto Integrador III-A — Análise e Desenvolvimento de Sistemas (EaD) — PUC Goiás, 2026.

Aplicação **cliente-servidor em linha de comando** que permite ao cliente do escritório parceiro
**Almeida Campos Advogados Associados** (direito médico) **consultar o andamento dos próprios processos**.
Toda a comunicação é **criptografada com TLS**.

O projeto foi desenvolvido com **Intent-Oriented Programming (IOP)**: a especificação de intenção
[`intencoes/sistema.iop`](intencoes/sistema.iop) é a fonte da verdade, e o código a implementa
componente por componente. Ver [`intencoes/README.md`](intencoes/README.md).

> ⚠️ **Protótipo acadêmico.** Todos os nomes, números de processo e informações do `dados.json`
> são **fictícios**. Nenhum dado real de clientes é usado (LGPD: dados de saúde são dados sensíveis).

## Intenções do usuário (funcionalidades)

| Intenção | O que faz |
|---|---|
| `autenticar` | Login com **CPF, CNPJ ou CRM** + senha |
| `consultar_meus_processos` | Lista os processos do cliente (número, tipo de ação, fase, última atualização) |
| `ver_andamento_do_processo` | Órgão julgador, fase, advogado, próximo passo e últimas movimentações |
| `encerrar_sessao` | Sai do sistema |

## Arquitetura

```
 intencoes/sistema.iop  ── fonte da verdade (System, Components, Flow, ErrorHandling)
          │ propriedades e mensagens lidas em tempo de execução
          ▼
┌───────────────────────┐   TLS 1.2/1.3 (TCP)    ┌─────────────────────────┐    ┌────────────┐
│ InterfaceDoCliente    │                        │ ServidorSeguro          │    │ dados.json │
│ ClienteDeRede         │ ─────────────────────▶ │ OrquestradorDeFluxos    │ ─▶ │ (fictício) │
│ CanalDeMensagens      │ ◀───────────────────── │ Validador / Controle /  │    └────────────┘
│ CanalSeguro           │  {"intencao": ...}     │ Consulta / Auditoria    │
└───────────────────────┘                        └─────────────────────────┘
```

**Protocolo:** uma mensagem JSON por linha. O cliente envia `{"intencao": "<nome>", ...dados}`.
O servidor responde `{"status": "ok", ...}` ou
`{"status": "erro", "condicao": "<ErrorHandling>", "mensagem": "..."}`.

## Segurança

| Mecanismo | Como foi feito |
|---|---|
| Comunicação criptografada | Módulo `ssl` do Python (TLS, versão mínima 1.2) com certificado X.509 |
| Autenticidade do servidor | O cliente valida o certificado (`cert.pem`) e o nome do host; certificado desconhecido → conexão abortada |
| Senhas | Nunca em texto puro: hash **PBKDF2-HMAC-SHA256** com salt aleatório e 200 mil iterações |
| Controle de acesso | Cada cliente só vê os **próprios** processos; tentativas negadas são registradas |
| Força bruta | Máximo de **3 tentativas** de login por conexão |
| Identificação | CPF/CNPJ com dígitos verificadores conferidos; CRM com UF válida. Documento inválido conta como tentativa |
| Enumeração de usuários | Mesma mensagem e mesmo tempo para documento não cadastrado ou senha errada |
| Auditoria | Log no terminal e em `logs/servidor.log`: senhas nunca registradas, documentos sempre **mascarados** (ex.: `CPF ***.444.777-**`) |
| Robustez | Limite de 64 KB por mensagem, tempo limite de inatividade, JSON validado |
| Chave privada | `certs/key.pem` fica fora do repositório (`.gitignore`) |

## Requisitos

- **Python 3.8 ou superior** — só a biblioteca padrão, **nada para instalar com pip**.
- **OpenSSL** apenas para gerar o certificado (no Windows, já vem com o **Git for Windows**).

## Como executar

Abra um terminal na pasta do projeto.

```bash
python gerar_certificado.py   # 1. só na primeira vez: cria certs/cert.pem e certs/key.pem
python servidor.py            # 2. terminal 1 (deixe aberto)
python cliente.py             # 3. terminal 2
```

### Usuários de demonstração (fictícios)

O cliente entra com **CPF, CNPJ ou CRM**, com ou sem pontuação. O CRM aceita número e UF
em qualquer ordem: `CRM-GO 99001`, `CRM/GO 99001`, `99001/GO`, `GO 99001`...
Os exemplos aparecem na tela antes da digitação.

| Cliente | Documento(s) | Senha | Processos |
|---|---|---|---|
| Maria Exemplo da Silva (paciente) | CPF `111.444.777-35` | `maria2026` | 2 |
| João Fictício Pereira (paciente) | CPF `222.555.888-46` | `joao2026` | 2 |
| Ana Teste Rodrigues (paciente) | CPF `333.666.999-57` | `ana2026` | 1 |
| Clínica Exemplo Saúde Ltda. | CNPJ `11.222.333/0001-81` | `clinica2026` | 1 |
| Dr. Carlos Modelo Andrade (médico) | CPF `444.777.111-07` **ou** CRM `CRM-GO 99001` | `medico2026` | 1 |

> Os documentos são **fictícios**: foram escolhidos só para ter dígitos verificadores válidos e não
> pertencem a nenhum cliente do escritório.

Para trocar uma senha: `python cadastrar_senha.py 111.444.777-35` (ou `python cadastrar_senha.py "CRM-GO 99001"`)

> Dica: rode o cliente no **Prompt de Comando / PowerShell / terminal**. Em alguns consoles de IDE,
> a digitação da senha (`getpass`) pode aparecer na tela ou travar.

### Usando duas máquinas na mesma rede

```bash
python gerar_certificado.py --ip 192.168.0.10     # IP da máquina do servidor
python servidor.py --host 0.0.0.0
# copie certs/cert.pem (NÃO a key.pem) para a máquina do cliente e rode:
python cliente.py --host 192.168.0.10
```

## Testes e verificação de intenções

```bash
python -m unittest discover -s tests -v   # 36 testes
python verificar_intencoes.py             # confere especificação ↔ código ↔ testes
```

## Estrutura

Os arquivos da raiz (`servidor.py`, `cliente.py`) são apenas **pontos de entrada**: leem as opções
da linha de comando, carregam a especificação e montam as peças. A lógica fica no pacote `app/`.

```
├── intencoes/
│   ├── sistema.iop             # ESPECIFICAÇÃO DE INTENÇÃO (fonte da verdade)
│   └── README.md               # método IOP aplicado e rastreabilidade
├── app/
│   ├── especificacao.py        # lê o sistema.iop
│   ├── intencao.py             # @componente, @fluxo, ErroDeIntencao
│   ├── modelos.py              # Documento, Cliente, Processo, Movimentacao
│   ├── documentos.py           # ValidadorDeDocumento (CPF, CNPJ, CRM)
│   ├── seguranca.py            # CanalSeguro, GerenciadorDeSenhas
│   ├── protocolo.py            # CanalDeMensagens
│   ├── repositorio.py          # RepositorioDeProcessos (abstrato), RepositorioJSON
│   ├── componentes_servidor.py # Validador, ControleDeAcesso, Consulta, Auditoria, Sessao
│   ├── componentes_cliente.py  # ClienteDeRede, InterfaceDoCliente
│   └── fluxos.py               # OrquestradorDeFluxos (seção Flow), ServidorSeguro
├── servidor.py                 # ponto de entrada: inicia o servidor
├── cliente.py                  # ponto de entrada: inicia o cliente
├── verificar_intencoes.py      # verificador intenção ↔ código ↔ testes
├── cadastrar_senha.py
├── gerar_certificado.py
├── dados.json                  # dados FICTÍCIOS
├── certs/                      # cert.pem e key.pem (não versionados)
├── logs/                       # servidor.log (não versionado)
└── tests/
```
