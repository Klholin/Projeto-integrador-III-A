# Intent-Oriented Programming (IOP) neste projeto

Este projeto segue o paradigma **Intent-Oriented Programming**: o sistema é descrito
primeiro como **intenção humana** e só depois implementado. A especificação
[`sistema.iop`](sistema.iop) é a **fonte da verdade**. O código Python é a realização dela.

## Esquema utilizado

| Seção | Papel | No projeto |
|---|---|---|
| `System` | Propósito e propriedades gerais | `ConsultaDeProcessos`: cliente-servidor, TLS, LGPD |
| `Components` | Unidades funcionais (inputs, outputs, action, properties) | 11 componentes |
| `Flow` | Sequências disparadas por gatilhos | `on conexão recebida` + 4 intenções do usuário |
| `ErrorHandling` | Condição de erro → resolução/mensagem | 10 condições |
| `ImplementationMap` | Como cada tipo de item vira código Python | Component, Flow, ErrorHandling |

## Ciclo de desenvolvimento (intenção → implementação)

1. **Especificação da intenção:** descrever ou alterar `System`, `Components`, `Flow` e `ErrorHandling` em `sistema.iop`.
2. **Seleção da implementação:** aplicar o `ImplementationMap` correspondente (classe `@componente`, método `@fluxo`, `ErroDeIntencao`).
3. **Geração do código:** a especificação é usada como *prompt estruturado* para a IA gerar o código (Padrão 1: *IOP as Prompt Structure*), seguindo os mapas (Padrão 2: *IOP with Implementation Maps*).
4. **Refinamento e validação:** revisar o código e rodar os testes e o verificador:
   ```
   python -m unittest discover -s tests -v
   python verificar_intencoes.py
   ```

## Como os princípios do IOP aparecem no código

| Princípio | Implementação |
|---|---|
| Alinhamento cognitivo humano | Intenções com nomes do domínio: `consultar_meus_processos`, `ver_andamento_do_processo` |
| Separação de interesses | `sistema.iop` (o quê) separado de `app/` (como) |
| Consistência estrutural | Todo componente segue o mesmo `ImplementationMap` (`@componente` + docstring "Intenção: ...") |
| Flexibilidade de implementação | `RepositorioDeProcessos` é abstrato; `RepositorioJSON` é uma das implementações possíveis |
| Transparência | `verificar_intencoes.py` confere intenção ↔ código ↔ testes |
| Compatibilidade com IA | Especificação estruturada, usada como prompt para gerar e regenerar o código |

**A especificação é executável em parte:** as `properties` (limite de tentativas, tamanho
máximo de mensagem, versão mínima do TLS, iterações do hash, campos expostos) e todas as
mensagens de `ErrorHandling` são lidas de `sistema.iop` em tempo de execução.
Exemplo: trocar `max_tentativas: 3` por `5` muda o comportamento do servidor sem mexer no código.

## Rastreabilidade

| Componente (intenção) | Implementação |
|---|---|
| CanalSeguro | `app/seguranca.py` → `CanalSeguro` |
| CanalDeMensagens | `app/protocolo.py` → `CanalDeMensagens` |
| GerenciadorDeSenhas | `app/seguranca.py` → `GerenciadorDeSenhas` |
| ValidadorDeDocumento | `app/documentos.py` → `ValidadorDeDocumento` |
| RepositorioDeProcessos | `app/repositorio.py` → `RepositorioDeProcessos` (abstrato) / `RepositorioJSON` |
| ValidadorDeCredenciais | `app/componentes_servidor.py` → `ValidadorDeCredenciais` |
| ControleDeAcesso | `app/componentes_servidor.py` → `ControleDeAcesso` |
| ConsultaDeProcessos | `app/componentes_servidor.py` → `ConsultaDeProcessos` |
| RegistroDeAuditoria | `app/componentes_servidor.py` → `RegistroDeAuditoria` |
| ClienteDeRede | `app/componentes_cliente.py` → `ClienteDeRede` |
| InterfaceDoCliente | `app/componentes_cliente.py` → `InterfaceDoCliente` |

| Fluxo (intenção) | Implementação | Testes |
|---|---|---|
| on conexão recebida | `app/fluxos.py` → `ServidorSeguro.conexao_recebida` | `test_canal_seguro_*` |
| on intenção autenticar | `app/fluxos.py` → `OrquestradorDeFluxos.autenticar` | `test_autenticar_*` |
| on intenção consultar_meus_processos | `app/fluxos.py` → `OrquestradorDeFluxos.consultar_meus_processos` | `test_consultar_meus_processos_*` |
| on intenção ver_andamento_do_processo | `app/fluxos.py` → `OrquestradorDeFluxos.ver_andamento_do_processo` | `test_ver_andamento_do_processo_*` |
| on intenção encerrar_sessao | `app/fluxos.py` → `OrquestradorDeFluxos.encerrar_sessao` | `test_encerrar_sessao` |

## Exemplo real de mudança guiada pela intenção

Pedido: *"o cliente deve se conectar usando CPF, CNPJ ou CRM"*.

1. **Intenção primeiro:** novo componente `ValidadorDeDocumento`, novo passo no Flow `autenticar`,
   nova condição `documento_invalido` e a propriedade `documentos: sempre mascarados` na auditoria.
2. **Verificador antes do código:** `27/29 verificações OK`, apontando `ValidadorDeDocumento` sem classe
   e `documento_invalido` sem uso. A especificação mostrou o que faltava implementar.
3. **Implementação** seguindo os ImplementationMaps, até o verificador voltar a `29/29` e os testes passarem.

## Regra para mudanças

> Toda mudança de comportamento começa na especificação. Se o código mudar sem a intenção
> mudar (ou o contrário), `verificar_intencoes.py` aponta a divergência.
