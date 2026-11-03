# Handoff para o Claude Code — abrir o épico do redesign

Cole o bloco abaixo na sua sessão do Claude Code, na raiz do repositório.

```markdown
Vamos abrir o épico do redesign do site. Tudo o que você precisa está em docs/redesign/:
ROADMAP.md (plano, 18 beads em 5 fases), design/*.png (referência visual) e
design/*.dc.html (fonte do desenho — só referência, tem números digitados de propósito).

Faça nesta ordem e pare para eu confirmar onde indicado:

1. Situação do git. Este checkout está no branch bd/scoutlens-uze.31 e o main do GitHub
   já tem D071–D072. Mostre `git status -sb` e o que falta para trazer o main local até
   origin/main. NÃO troque de branch nem faça pull sem eu confirmar.

2. Número da decisão. Depois de atualizado, veja a próxima decisão livre em
   docs/decisions-log.md. O ROADMAP chama de D073; se não for, me diga qual é.

3. Beads. Rode `bd create --help` e `bd dep --help` para usar a sintaxe desta versão.
   Proponha (sem executar ainda) os comandos para:
   - um épico "Redesign Yumusarái Labs" com descrição apontando para docs/redesign/ROADMAP.md;
   - as 18 beads da tabela "Fases e beads", como filhas do épico, com título, labels
     (frontend / product-narrative / delegable como na tabela), e na descrição:
     arquivos que a bead pode tocar + critério "Pronta quando";
   - dependências: cada bead da fase N depende de todas as beads da fase N-1
     (fase 0 não depende de nada; rdz.7 e rdz.11 sem dependência entre si).
   Mostre a lista e espere meu ok. Depois execute e mostre `bd ready`.

4. Commit dos documentos. Proponha um branch bd/<id-do-épico> com só docs/redesign/**
   e a mensagem de commit. Não faça commit nem push sem eu autorizar.

Regras: siga docs/frontend-agent-contract.md; nunca edite .beads/ à mão; stage só
docs/redesign/**.
```

## Como manter o roadmap atualizado

- **Status vive no beads.** Fechar, bloquear e reabrir beads é o que conta; `bd ready` diz o próximo passo.
- **ROADMAP.md muda só quando o escopo muda** (bead nova, fase reordenada, decisão tomada). Peça ao Claude Code: "atualize docs/redesign/ROADMAP.md com <mudança> e abra um PR".
- **Decisões da seção "Decisões que são suas"**: marque a caixa no ROADMAP.md quando decidir e registre a escolha na decisão do redesign em `decisions-log.md`.
- **O doc online** (Claude Docs) é a versão para ler e comentar. Se quiser ele sincronizado com o repo, peça na conversa onde ele foi criado.
