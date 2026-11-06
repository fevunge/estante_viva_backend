# AGENTS.md — Regras para agentes (Estante Viva / backend)

Este arquivo vale para qualquer agente (humano ou IA) que altere este repositório.
Leia **antes** de tocar em qualquer arquivo.

## 0. Ordem de prioridade

1. Pedido explícito do usuário na conversa.
2. [`docs/SPEC.md`](docs/SPEC.md) — verdade sobre produto, rotas, auth, API e dados.
3. Este `AGENTS.md` — regras de processo.

Se o pedido do usuário contrariar o SPEC, **pare e pergunte** qual deve valer.
Nunca "resolva" o conflito escolhendo sozinho.

## 1. Leitura obrigatória antes de agir

- Ler `docs/SPEC.md` **inteiro** antes de qualquer mudança de comportamento.
- Ler os arquivos envolvidos (`read`/`grep`) antes de editar. Não editar por suposição.
- Se o SPEC não cobrir o caso, isso é motivo para perguntar, não para inventar.

## 2. Não quebre o projeto

- **Diff mínimo.** Altere só o necessário para a tarefa. Nada de refactor amplo, renomeação em massa ou "limpeza" não pedida.
- **Não reescreva arquivo que funciona** para impor estilo. Siga o padrão já existente (nomes, imports, tratamento de erro, tipagem).
- **Não apague nem mova** arquivos, rotas, campos de modelo ou coleções sem confirmação explícita do usuário.
- **Dependências:** não adicione pacote sem necessidade real; não altere versões pinadas (`fastapi==`, `pymongo==`, `motor==`, `pypdf==`, `pypdfium2==`, `bcrypt==`) sem pedido. Toda dependência nova deve ser justificada na resposta.
- **Nunca reintroduza** `emergentintegrations` nem qualquer pacote privado do emergent.ai.
- **Não toque** em `.venv/`.
- **Não altere** o `addopts` do `pytest.ini` (`-n 2 --dist loadscope`). O próprio arquivo proíbe.
- **Nada destrutivo:** sem `DROP`/`delete_many({})` em coleções reais, sem `rm -rf`, sem `git reset --hard`, sem sobrescrever `.env`.
- **Segredos:** nunca commitar `.env`, chaves do Clerk, `MONGO_URL` ou credenciais. Use `.env.example` com placeholders.
- Preserve o contrato atual: rotas em `/api`, respostas e códigos de status descritos no SPEC, isolamento por `user_id` ("não é seu" = 404).

## 3. Não alucine

- Só cite/use o que **existe no repositório**. Confirme assinaturas, nomes de campos e imports lendo o código.
- Não invente endpoints, variáveis de ambiente, modelos, bibliotecas, versões ou comportamento de serviço externo.
- Se não souber, diga **"não sei"** e pergunte. Chutar é pior que admitir.
- Não afirme que algo "funciona" sem ter rodado a verificação correspondente.
- Não invente saída de comando, resultado de teste ou log.

## 4. Não fique preso (limite de esforço)

Orçamento por subproblema:

- **Máx. 3 tentativas** para o mesmo erro/abordagem. Se falhou 3x, mude de estratégia ou pare.
- **Máx. ~10 minutos** sem progresso mensurável (arquivo alterado, erro entendido, teste passando).
- **Máx. 2 minutos** por comando em primeiro plano. Comandos longos (install, build, testes) devem usar timeout e ser avisados ao usuário.
- Nunca repetir o **mesmo comando** esperando resultado diferente.
- A cada ~10 chamadas de ferramenta sem resultado tangível, faça um checkpoint e reporte o estado.

Ao atingir o limite, **pare e fale com o usuário**, informando:

1. o objetivo;
2. o que já foi tentado (comandos e erros reais);
3. onde travou;
4. hipóteses;
5. opções de caminho (com prós/contras).

## 5. Quando perguntar (obrigatório)

Pare e pergunte quando:

- o pedido for ambíguo ou puder ser interpretado de mais de uma forma;
- houver conflito com `docs/SPEC.md`;
- a mudança afetar **contrato de API**, **schema de dados**, **auth/Clerk** ou fluxo de admin;
- for necessário apagar/renomear dados ou arquivos;
- faltar variável de ambiente, serviço externo ou credencial;
- o limite de esforço da seção 4 for atingido.

Para decisões pequenas e reversíveis, escolha a opção mais conservadora e registre a escolha na resposta.

## 6. Ambiente e comandos de referência

Python 3.12 gerenciado por `mise` (`mise.toml`); venv em `.venv/`.

```bash
# dependências
uv pip install -r requirements.txt

# servidor (porta usada pelos testes)
.venv/bin/uvicorn server:app --reload --port 8001

# testes (exigem servidor rodando em :8001)
.venv/bin/pytest

# sanidade de import (exige .env válido)
.venv/bin/python -c "import server"
```

Variáveis esperadas pelo código: `MONGO_URL`, `DB_NAME`, `CORS_ORIGINS`, `APP_TZ`,
`ADMIN_EMAIL`, `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`.
Sem `MONGO_URL`/`DB_NAME`, `lib/db.py` falha no import.

## 7. Verificação antes de dizer "pronto"

- Rode a verificação mais próxima do que mudou (import, teste específico, chamada de endpoint).
- Informe **exatamente** os comandos executados e o resultado (sucesso/erro).
- Se não foi possível verificar (ex.: falta `.env`/Mongo), diga isso explicitamente e explique o que ficou pendente.
- Nunca declare concluído algo cuja verificação falhou.

## 8. Formato da resposta final

- Resumo curto do que mudou e por quê.
- Arquivos alterados (caminhos).
- Comandos rodados + resultado.
- Pendências, riscos e perguntas abertas.

## 9. Escopo

- Este workspace é o **backend** (`/home/fevunge/book/backend`). O frontend fica em `../frontend` — só mexa nele se o usuário pedir.
- Strings voltadas ao usuário em **pt-BR**; código segue o padrão atual do projeto.
- O SPEC descreve o produto; não implemente features fora dele sem pedido.
