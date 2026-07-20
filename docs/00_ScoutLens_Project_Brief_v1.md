# ScoutLens — Project Brief v1 (source document)

> This file preserves the original spike brief as submitted, verbatim, as the
> immutable specification the project charter operationalizes. If the charter
> or decisions log diverge from this brief, the divergence must be explicit
> and justified in `project-charter.md` and `decisions-log.md` — this file
> itself is never edited to match later decisions.

**Status:** frozen at intake, 2026-07-20.

**Decision question (must remain unchanged for the duration of the spike):**

> Is there enough signal in the available event data to justify ScoutLens as
> a flagship project?

---

Vou tratar o brief enviado como a **especificação inicial oficial do spike**. A pergunta de decisão está correta e deve permanecer imutável durante as duas semanas:
> **Is there enough signal in the available event data to justify ScoutLens as a flagship project?**
A proposta abaixo operacionaliza o brief sem antecipar arquitetura final, UI, agente, RAG ou modelo sofisticado.
Há também uma boa notícia inicial sobre os dados: o artigo original declara que os datasets são disponibilizados sob **CC BY 4.0** e descreve aproximadamente 1.941 partidas, 3,25 milhões de eventos e 4.299 jogadores nas cinco ligas e duas competições internacionais. O dataset de partidas inclui lineups, banco e substituições; o de jogadores inclui um `role` principal; e os eventos possuem tipo, subtipo, tags, tempo e coordenadas normalizadas. Isso torna o spike plausível, mas **não elimina a auditoria artefato a artefato nem garante que minutos e posições detalhadas sejam triviais de reconstruir**. (Pappalardo et al., Scientific Data / Nature)

# 1. Project charter resumido

## ScoutLens — Feasibility Spike Charter

**Working title**
ScoutLens — Evidence-Based Football Recruitment & Player-Role Intelligence

**Timebox**
10 dias úteis / aproximadamente 2 semanas.

**Problema**
Avaliar se dados públicos de eventos de futebol contêm informação suficiente para construir representações de papel de jogador que sejam reproduzíveis, interpretáveis e temporalmente estáveis.

**Research question**
> Can football event data be used to build stable, interpretable player-role representations that support evidence-based recruitment searches?

**Decisão ao final**
`GO`, `PIVOT` ou `KILL`.

**Unidade analítica principal**
`player × temporal period`
Provavelmente jogador por metade cronológica da temporada, condicionado à disponibilidade de minutos suficientes em ambos os períodos.

**Experimento primário**
Temporal Role Stability Experiment.

**Método inicial**
Features event-derived agregadas e normalizadas + similaridade simples.
Não há autorização conceitual, neste momento, para introduzir:
* deep learning;
* embeddings aprendidos;
* clustering;
* LLM;
* agente;
* RAG;
* interface de usuário.
Esses componentes precisam conquistar seu lugar posteriormente.

**Usuário final hipotético**
Analista de recrutamento ou scout utilizando análise quantitativa para identificar jogadores que merecem investigação adicional.

**Claim máximo permitido após o spike**
> Event-derived profiles show sufficient evidence of [stable / unstable] player-role signal to justify [continuing / restricting / discontinuing] the ScoutLens research program.

Não:
> ScoutLens finds the best players to sign.

**Primary success condition**
Demonstrar, quantitativamente, que uma representação baseada em eventos contém sinal de identidade/papel ao longo do tempo e que esse sinal não é explicado apenas de forma trivial por posição nominal, minutos ou volume de participação.

# 2. Matriz hipótese → evidência → experimento → métrica → decisão

| Hipótese                          | Evidência necessária                                                  | Experimento                                                      | Métricas principais                                                 | Critério preliminar                                                                  |
| ---------------------------------- | ----------------------------------------------------------------------| ------------------------------------------------------------------| -----------------------------------------------------------------------| ---------------------------------------------------------------------------------------|
| **H1 — Data Coverage**             | População elegível suficientemente grande e distribuída               | Reconstrução de minutos + filtros de elegibilidade                | jogadores totais; elegíveis; por liga/role; minutos por split         | GO: população ampla; PIVOT: população útil porém restrita; KILL: cobertura inviável   |
| **H2 — Feature Feasibility**       | Features semanticamente defensáveis e com cobertura                   | Feature audit por família                                         | cobertura; missingness; distribuição; casos inválidos                 | GO: múltiplas dimensões confiáveis; PIVOT: conjunto limitado mas útil                 |
| **H3 — Temporal Stability**        | Perfil do período A relacionado ao mesmo jogador/perfil no período B  | Temporal Role Stability                                           | MRR; Recall@K; median rank; neighborhood overlap                      | Sinal deve superar baseline trivial com incerteza quantificada                        |
| **H4 — Beyond Position**           | Sinal permanece quando posição deixa de resolver o problema           | Retrieval dentro da mesma role + comparação de baselines          | MRR/Recall@K within-role; delta vs baseline                           | GO se houver informação incremental além de role/minutos                              |
| **H5 — Baseline Competitiveness**  | Complexidade só é admitida mediante ganho                             | Baseline A vs B; modelos posteriores ficam fora do gate inicial   | métricas de retrieval + bootstrap CI                                  | Método simples permanece padrão até ser superado                                      |
| **H6 — Context Effects**           | Medir influência de liga, equipe e volume                             | Estratificação e análise de vizinhanças                           | league/team concentration; minute sensitivity; resultados por liga    | PIVOT se representação for predominantemente contextual                               |
| **H7 — Agentic Feasibility**       | NL → constraints sem perda                                            | Não executar neste spike                                          | —                                                                      | Não é gate das duas semanas                                                           |

### Baseline A — trivial
Proponho formalizá-lo como:
> **same nominal role → nearest minutes played**

Isso torna explícito o que estamos tentando superar.

### Baseline B — primeiro baseline analítico real
> standardized per-90 event-derived features → cosine similarity

Este é o verdadeiro adversário do futuro "modelo sofisticado".
Se ele funcionar muito bem, isso é um **resultado**, não um problema. O erro seria adicionar complexidade para melhorar a aparência do projeto.

# 3. Duas correções metodológicas importantes antes de começar

## 3.1 Minutos são uma variável crítica, não apenas um filtro

O dataset de matches possui `lineup`, `bench` e `substitutions`, portanto existe base para reconstruir tempo em campo. Porém o algoritmo precisa lidar com:
* titulares;
* substitutos que entram;
* jogadores substituídos;
* jogadores expulsos;
* partidas com formação ausente;
* acréscimos;
* eventualmente extra time.

O paper documenta explicitamente lineups, banco e substituições, mas isso não significa que podemos assumir uma função trivial `90 - substitution_minute`. A reconstrução precisa virar um componente testado.

**Minha recomendação:** minutos jogados deve ser o primeiro "hard problem" do pipeline depois da ingestão.

## 3.2 Não assumir que temos posição match-level

O dataset de players oferece um `role` principal. O paper também descreve que os operadores configuram formações e posições durante a coleta, mas a descrição pública do schema de `teamsData` enfatiza lineup, bench e substitutions; não devemos assumir, antes de inspecionar os JSONs, que a posição detalhada por partida está efetivamente disponível no artefato público.

Isso pode ser relevante.

Se só houver algo como:
* Goalkeeper;
* Defender;
* Midfielder;
* Forward,

então **posição nominal será um baseline extremamente grosseiro**, o que na verdade torna H4 ainda mais interessante.

# 4. Plano detalhado das duas semanas

## Semana 1 — Data feasibility

### Dia 1 — Provenance e aquisição
Objetivo: localizar os artefatos canônicos; registrar versão; registrar DOI; registrar URLs de aquisição; registrar licença; gerar manifest; baixar os dados fora do Git.

A coleção Figshare atualmente exposta possui versão 5; o artigo científico afirma CC BY 4.0 para os datasets. Mesmo assim, o manifest deve registrar cada artefato consumido individualmente.

**Entregável:** `docs/data-provenance.md` e um manifest com colunas:
`artifact, source_url, source_version, retrieved_at, checksum, declared_license, citation, redistribution_status`

### Dia 2 — Schema profiling
Inspecionar: competitions, matches, teams, players, events, tag mapping. Não ingerir coaches ou referees inicialmente.
Produzir: row counts, schemas observados, tipos, chaves, cardinalidades, unknown/sentinel IDs, missingness, exemplos de registros.
**Entregável:** `docs/data-dictionary.md`

### Dia 3 — Integridade relacional e Data Quality v0
Testar: `event.matchId → matches.wyId`, `event.playerId → players.wyId`, `event.teamId → teams.wyId`, `match.competitionId → competitions.wyId`.
Medir: eventos órfãos, jogadores desconhecidos, IDs duplicados, partidas sem eventos, partidas sem formation, eventos fora de sequência, timestamps anômalos, coordenadas fora do domínio esperado.
As coordenadas públicas são descritas como percentuais `[0,100]`, orientadas pela perspectiva ofensiva da equipe, o que facilita features espaciais, mas essa propriedade também deve ser testada empiricamente na ingestão.

### Dia 4 — Reconstrução de minutos
Implementar a primeira versão testável. Produzir, no mínimo: `player_id, match_id, team_id, started, minute_in, minute_out, minutes_played, derivation_status`.
Não esconder casos duvidosos. `derivation_status` ∈ {clean, missing_formation, substitution_conflict, dismissal_uncertain, invalid}.
Validar por invariantes: nenhum jogador com minutos negativos; nenhum jogador acima da duração máxima admissível sem explicação; número plausível de jogadores simultaneamente em campo; consistência entre starting XI e substituições.

### Dia 5 — Eligible population e Gate 1 preliminar
Definir diferentes thresholds: season minutes ≥450 / ≥900 / ≥1350. Para temporal retrieval: minimum minutes in period A e B.
Sugestão inicial para o experimento primário: **≥450 minutos em cada split** — tratado como parâmetro de sensibilidade, não dogma.
Produzir: total de jogadores, elegíveis, elegíveis por liga, elegíveis por role, distribuição de minutos, perda populacional por filtro.
**Checkpoint de sexta-feira:** `ScoutLens Data Feasibility Report — v0.1`

## Semana 2 — Modeling feasibility

### Dia 6 — Feature definition v0
~20–40 features, não centenas. Famílias: passing, progression, chance creation, shooting, defensive actions, spatial tendencies, possession/on-ball involvement, sequence involvement, carrying (tratado como derived proxy, nunca ground-truth).

### Dia 7 — Baselines + temporal split
Split cronológico determinístico por competição (ordenar partidas por `dateutc`, definir ponto de corte). Não dividir eventos individualmente ao meio. Calcular `player_profile_period_A` / `_B`, normalização per-90. Executar Baseline A e Baseline B.

### Dia 8 — Temporal Role Stability Experiment
Para cada jogador elegível em A e B: profile A como query, profiles B como candidate pool, ordenar candidatos, encontrar posição do próprio jogador. Métricas: MRR, median rank, Recall@1/5/10. Duas condições: global retrieval e within-role retrieval. Bootstrap para intervalos de confiança dos deltas entre métodos.

### Dia 9 — Context diagnostics e error analysis
Estratificar por role, liga, minutos. Analisar vizinhanças (estáveis/instáveis, dominadas por volume/equipe/liga). Intuição futebolística entra na investigação de casos, não na métrica primária.

### Dia 10 — Decision review
Congelar resultados. Não começar "só mais um modelo". Produzir o **ScoutLens Data & Modeling Feasibility Report** com: Executive Summary, Research Question, Data Provenance, License Assessment, Dataset Audit, Eligible Population, Feature Definitions, Temporal Split, Baselines, Temporal Stability Results, Position/Minutes/League Diagnostics, Qualitative Error Analysis, Known Limitations, GO/PIVOT/KILL Decision, Recommended Next Experiment.

# 5. Checklist de aquisição e auditoria Wyscout

## Provenance e licença
Usar Figshare/paper original como fontes canônicas; registrar DOI e versão da coleção; inventariar cada artefato; registrar licença declarada, citação exigida, data de download, checksum; documentar transformações; separar licença do código do ScoutLens da licença dos dados; não assumir herança automática de licença sem registrar evidência; não adicionar raw data ao Git por padrão.

**Avaliação inicial:** o paper afirma CC BY 4.0 para os datasets, portanto não há hoje um bloqueio evidente de licença para o spike. Recomendação: distribuir código de aquisição + manifest, não milhões de eventos no repositório, mesmo que a redistribuição seja licenciada.

## Estrutura
Contagens por competição/match/player/event type-subtype; cardinalidade de tags; schemas reais versus documentação; campos opcionais.

## Integridade
Unique event IDs; referential integrity; unknown player/team IDs; matches without events/formation; duplicated events; timestamp/period anomalies; coordinate bounds.

## Jogadores
Distribuição de main role; missing role; confirmar granularidade real das posições; auditar `birthDate`; não usar `currentTeamId` como representação histórica sem validação; derivar team affiliation a partir das partidas/eventos quando necessário.

## Minutos
Starting XI, bench, substitution in/out, expulsões, missing formations, extra time, regras de arredondamento, testes unitários para casos sintéticos, distribuição final de minutos.

## Eventos/features
Semântica dos event types/subevents; mapping das tags; orientação espacial; eventos sem player/positions; origem/destino por tipo; feature definitions versionadas.

# 6. Estrutura inicial do repositório

```text
scoutlens/
├── README.md
├── pyproject.toml
├── .gitignore
├── LICENSE
├── DATA_LICENSES.md
│
├── configs/
│   └── spike.yaml
│
├── data/
│   └── README.md
│
├── docs/
│   ├── project-charter.md
│   ├── data-provenance.md
│   ├── data-dictionary.md
│   ├── feature-definitions.md
│   ├── methodology.md
│   ├── limitations.md
│   └── feasibility-report.md
│
├── notebooks/
│   ├── 01_data_audit.ipynb
│   ├── 02_population_analysis.ipynb
│   ├── 03_feature_exploration.ipynb
│   └── 04_temporal_stability.ipynb
│
├── src/
│   └── scoutlens/
│       ├── data/
│       │   ├── ingestion.py
│       │   ├── validation.py
│       │   └── minutes.py
│       ├── features/
│       │   ├── definitions.py
│       │   └── aggregation.py
│       └── evaluation/
│           ├── similarity.py
│           ├── retrieval.py
│           └── temporal.py
│
├── tests/
│   ├── data/
│   ├── features/
│   └── evaluation/
│
└── artifacts/
    └── README.md
```

Não criar agora: `api/`, `agents/`, `rag/`, `frontend/`, `services/`, `kubernetes/`, `mlops/` — arquitetura por antecipação.

# 7. Estratégia notebook sem virar notebook-only

Regra: **notebooks ask questions, modules produce answers reproducibly.**

Ciclo: explore in notebook → identify reusable logic → move logic to src/ → add tests → notebook imports src/ → produce analysis.

Regras adicionais: notebook deve executar do zero; ordem das células deve ser válida; configuração importante não fica escondida em uma célula; resultados finais são produzidos por funções testáveis; random seeds explícitas; tabelas/gráficos regeneráveis; experimentos relevantes recebem configuração/versionamento, não nomes como `final_final_v2.ipynb`.

# 8. Critérios formais de GO / PIVOT / KILL

## Gate 0 — Provenance
GO: fontes canônicas identificadas, licença documentada, aquisição reproduzível. PIVOT: uso permitido mas não redistribuição — repo fornece downloader/instruções. KILL: direitos/provenance insuficientemente claros.
**Situação atual:** probable GO, pendente de manifest artefato a artefato.

## Gate 1 — Data
Thresholds como critérios de trabalho revisáveis, não verdades científicas.
GO: ~≥1.000 jogadores elegíveis (ou evidência de que população menor basta); cobertura útil em múltiplas roles; ≥3 ligas com população substancial (idealmente 5); minutos confiáveis para ≥95% da população candidata; integridade dos joins ≥99,5% (ou exceções explicadas); nenhuma família crítica de features inviabilizada por missingness estrutural.
PIVOT: ~500–999 elegíveis; ou só algumas roles com cobertura suficiente; ou poucas ligas comparáveis. Exemplo: "ScoutLens becomes a midfielder-role analysis prototype rather than a broad recruitment system."
KILL: população pequena demais mesmo após flexibilização defensável; minutos impossíveis de reconstruir; inconsistências fundamentais; ausência das dimensões de evento necessárias.

## Gate 2 — Analytical signal
GO: baseline event-derived supera materialmente role+minutes; ganho com CI consistente em ≥1 métrica primária; sinal mantido within-role; não degrada completamente nos estratos principais; erros investigáveis/explicáveis.
Métrica primária: MRR do same-player temporal retrieval; secundárias: Recall@5, Recall@10, median rank. Sem número mágico fixo — critério é improvement over baselines + confidence interval + robustness across strata.
PIVOT: sinal existe mas só em algumas roles / minutos baixos destroem resultado / efeitos contextuais fortes / baseline simples já captura quase tudo. Ex: "Event-derived statistical profiles support stable role similarity, but there is no evidence yet that learned representations add value."
KILL: resultados equivalentes a aleatoriedade dentro de posição; retrieval explicado praticamente só por minutos/volume; perfis altamente instáveis; ausência de estratégia de avaliação convincente.

# 9. Definition of Done do spike

Charter; data provenance document; license/redistribution assessment; versioned data manifest; reproducible acquisition process; initial data dictionary; automated core data validations; tested minutes derivation; eligible-player analysis; versioned feature definitions; deterministic temporal split; Baseline A; Baseline B; same-player temporal retrieval experiment; global evaluation; within-role evaluation; role/minutes/league stratification; qualitative error analysis; known limitations; reproduction instructions; GO/PIVOT/KILL explicitly recorded.

Condição adicional: **não pode haver um notebook com "resultado final" que dependa de executar manualmente células em ordem implícita.**

# 10. Primeiras tarefas concretas, por dependência

```text
SLS-001  Record project charter
    ↓
SLS-002  Create canonical source inventory
    ↓
SLS-003  Create data/license manifest
    ↓
SLS-004  Implement reproducible download/acquisition
    ↓
SLS-005  Profile raw schemas
    ↓
SLS-006  Implement raw-data validation
    ↓
SLS-007  Validate relational keys
    ↓
SLS-008  Audit formation/substitution coverage
    ↓
SLS-009  Implement minutes derivation
    ↓
SLS-010  Test minutes derivation
    ↓
SLS-011  Compute eligible population
    ↓
SLS-012  DATA GATE
    ↓
SLS-013  Define feature catalog v0
    ↓
SLS-014  Implement player-period aggregation
    ↓
SLS-015  Implement chronological split
    ↓
SLS-016  Implement baseline A
    ↓
SLS-017  Implement baseline B
    ↓
SLS-018  Run temporal retrieval
    ↓
SLS-019  Run within-role retrieval
    ↓
SLS-020  Context/minutes diagnostics
    ↓
SLS-021  Error analysis
    ↓
SLS-022  MODELING GATE
    ↓
SLS-023  Write final feasibility report
```

**A primeira linha de código útil do ScoutLens deveria estar mais próxima de "baixar e validar dados" do que de "calcular embeddings".**

# 11. Maiores incógnitas técnicas, em ordem de risco

1. **Minutos jogados** — sem denominadores confiáveis, per-90 features são garbage-in, garbage-out.
2. **Estabilidade após controlar posição** — risco existencial da tese analítica; se midfielder≈midfielder for praticamente todo o resultado, ScoutLens não tem uma representação de role interessante.
3. **Estabilidade versus quantidade de observação** — jogador pode parecer "instável" só por ter poucos minutos; exige curva minimum-minutes → population size → temporal stability.
4. **Team/context effect** — same-player retrieval alto não prova sozinho que descobrimos "role"; medir concentração de vizinhos por equipe/liga, usar within-role retrieval.
5. **Granularidade de posição** — dataset de players tem apenas `main role`; disponibilidade de posição match-level precisa ser verificada.
6. **Semântica de "progression"** — não é campo mágico do dataset; precisa de definição própria e justificada em `feature-definitions.md`.
7. **Carrying e off-ball behavior** — carries, off-ball movement, pressing intensity, physical intensity ficam explicitamente fora do claim sem dados apropriados.
8. **Evaluation target** — same-player retrieval testa estabilidade, não valida qualidade de recrutamento diretamente. Isso entra nas limitações desde o primeiro relatório: "Stable role representations are a prerequisite for recruitment-oriented similarity search, not proof that the resulting shortlist leads to better recruitment decisions."

# Decisão original do autor do brief

**GO para o feasibility spike. Não é ainda GO para o flagship de 8–12 semanas.**

Próximo passo de maior impacto proposto originalmente: executar SLS-001 a SLS-003 antes de modelar qualquer coisa (Project Charter → Canonical Source Inventory → Data/License Manifest), depois aquisição e schema profiling.

Maior risco imediato: reconstrução confiável de minutos reduzir muito a população elegível. Maior risco analítico: similaridade dominada por posição, volume ou contexto de equipe. Nenhum dos dois é razão para alterar a ideia — são precisamente as hipóteses que justificam o spike.

Arquivos de origem propostos: `01_ScoutLens_Feasibility_Spike_Plan_v1.md` (este documento) e `00_ScoutLens_Project_Brief_v1.md` (este próprio arquivo).
