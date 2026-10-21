# Impacto do Jitter sobre Violações Temporais em uma Federação micro-LF

Experimento V0 desenvolvido na disciplina **Redes de Comunicação em Sistemas
Físico-Cibernéticos da UFCG**.

O objetivo é avaliar como a variabilidade induzida na comunicação afeta a taxa
de mensagens tardy/STP em uma federação micro-LF, com maxwait e demais
condições controlados. A pergunta experimental é: **como diferentes níveis
do parâmetro de jitter configurado no NetEm influenciam a taxa tardy com
maxwait fixo?**

**Tardy/STP não equivale a deadline miss. Maxwait não é deadline.**

## Arquitetura e configuração

```text
Sender -> TCP / NetEm no loopback -> Receiver
```

Sender e Receiver são federados reais em processos distintos, executados no
mesmo Ubuntu/WSL2, com backend native do micro-LF. O runtime
[reactor-uc](https://github.com/lf-lang/reactor-uc) e seu compilador foram
fixados no commit `e2d9a9fa79620f4f9152ebff2350884e5b5bcb0a`.
Nenhum arquivo vendor/submodule foi modificado.

| Parâmetro | Valor |
| --- | --- |
| maxwait explícito do Receiver | 20 ms |
| Período de emissão | 50 ms |
| Atraso-base configurado em C0–C3 | 10 ms |
| Jitter configurado C0 / C1 / C2 / C3 | 0 / 5 / 10 / 15 ms |
| Distribuição nos cenários com jitter | normal |
| Warm-up por execução | 10 eventos, excluídos da taxa |
| Eventos medidos por execução | 100 |
| Replicações finais por cenário | 5 |
| Runs finais C0–C3 válidos | 20/20 |
| Seed mestre | 20261020 |

C0 usa NetEm com atraso de 10 ms e jitter zero. B0, coletado antes e depois
da campanha final, usa ausência de NetEm e é um sanity check separado.
O jitter foi introduzido somente na rede, sem atrasos artificiais nas reações.

## Resultados principais

Dados coletados em 21/10/2026 na campanha `v0_20261021T140846_final`.
Taxas tardy médias entre as cinco replicações:

| Cenário | Jitter configurado | Taxa tardy média | IC 95% exploratório |
| --- | ---: | ---: | ---: |
| C0 | 0 ms | 2,0% | 0,8–3,6% |
| C1 | 5 ms | 8,2% | 5,4–10,6% |
| C2 | 10 ms | 23,2% | 19,8–28,8% |
| C3 | 15 ms | 30,4% | 29,4–31,4% |

Os intervalos usam 10.000 reamostragens bootstrap **por run**, com seed fixa.
Cada run válido tem exatamente 100 envios medidos e 100 recebimentos, sem
ausências nem duplicatas. A taxa usa denominador fixo de 100 eventos;
o warm-up não entra no cálculo. O piloto foi informativo e os parâmetros
foram congelados antes da campanha, sem calibração.

![Taxa tardy por jitter configurado](experiment_v0_final/results/figures/tardy_rate_vs_jitter.png)

- [Relatório científico completo](experiment_v0_final/REPORT.md)
- [Relatório do piloto](experiment_v0_final/PILOT_REPORT.md)
- [Resultados finais por execução](experiment_v0_final/results/processed/results.csv)
- [Resumo estatístico](experiment_v0_final/results/processed/summary.csv)
- [Gráfico em PDF](experiment_v0_final/results/figures/tardy_rate_vs_jitter.pdf)
- [Auditoria final](experiment_v0_final/logs/final_audit.json)

O CSV final inclui também os dois B0, separados dos 20 runs C0–C3 nas
estatísticas e no gráfico principal. `all_runs.csv` preserva todas as fases,
inclusive um probe inicial inválido, que não entrou nas estatísticas finais.

## Limitações

Sender e Receiver usam a mesma máquina e loopback. NetEm também afeta ACKs e
tráfego de controle; TCP pode introduzir ordenação e bloqueio head-of-line.
O host/WSL não é hard real-time, e cinco replicações dão somente intervalos
exploratórios. A distribuição NetEm é artificial: parâmetros configurados
não equivalem aos valores observados, e o atraso físico médio pode variar.

As métricas secundárias de atraso medem envio na aplicação até execução da
reação de entrada, incluindo runtime e escalonamento. Os resultados deste V0
não generalizam diretamente para uma rede industrial real nem estabelecem
que mais jitter sempre causará mais tardy. Campanhas futuras devem estudar
dois hosts físicos, sincronização de relógios e precisão estatística.

## Estrutura

```text
microLF-jitter-experiment/
├── README.md
├── .gitignore
├── .gitattributes
└── experiment_v0_final/
    ├── src/                 # Programa micro-LF e template de parametrização
    ├── scripts/             # Build, coleta, validação, análise e gráficos
    ├── config/              # Parâmetros, toolchain e hashes congelados
    ├── logs/                # Ambiente, auditorias e manifesto de integridade
    ├── results/
    │   ├── raw/             # Logs, metadados e registros tc por fase/run
    │   ├── processed/       # CSVs, eventos unidos por seq e estatísticas
    │   └── figures/         # Figuras PNG/PDF já produzidas
    ├── EXPERIMENT_SPEC.md
    ├── PILOT_REPORT.md
    ├── README.md
    ├── REPORT.md
    └── requirements.txt
```

Código gerado, binários, builds, caches e cópias compactadas locais não são
versionados. Fontes, scripts, configuração, dados brutos, dados processados,
figuras e evidências de auditoria permanecem no repositório. `.gitattributes`
preserva os bytes dos arquivos para manter os hashes científicos entre
checkouts Linux e Windows.

## Reprodução

Consultar primeiro as [instruções completas do experimento](experiment_v0_final/README.md).
Requisitos: Linux com suporte a `sch_netem`, privilégios para configurar
`tc` em `lo`, Git, GCC, CMake, Java 17, Python 3 e curl. As versões usadas
estão registradas no relatório e nos logs. O setup instala o toolchain
fixado e as dependências da análise em área local do usuário.

Para uma nova coleta, preserve os dados publicados e crie outra área:

```bash
git clone https://github.com/MarcusPereirinha/microLF-jitter-experiment.git
cd microLF-jitter-experiment/experiment_v0_final
bash scripts/new_replication.sh "$HOME/microlf-v0-reproduction"
cd "$HOME/microlf-v0-reproduction"
bash scripts/setup_toolchain.sh
sudo -v
bash scripts/check_env.sh --netem-test
bash scripts/build.sh
bash scripts/run_one.sh B0 0 0 1 20261020 sanity implementation
bash scripts/campaign_terminal.sh
```

O script executa probe, piloto e, se houver sensibilidade suficiente,
campanha final, análise e relatório. NetEm no loopback pode afetar outros
serviços locais; os scripts recusam substituir qdisc preexistente e removem
o qdisc do experimento ao sair. Uma nova execução real pode produzir taxas
diferentes, mesmo com plano e seeds iguais.

Para reconstruir somente CSVs/estatísticas ou figuras dos logs existentes,
sem executar federados ou aplicar NetEm, após disponibilizar as dependências:

```bash
cd microLF-jitter-experiment/experiment_v0_final
source config/toolchain.env
"$ANALYSIS_PYTHON" scripts/analyze.py --campaign v0_20261021T140846_final
# Para recriar somente figuras a partir dos CSVs:
"$ANALYSIS_PYTHON" scripts/plot.py
```

Esses comandos são instruções de reprodução; a preparação deste repositório
preservou integralmente os resultados, gráficos e código científico existentes.
