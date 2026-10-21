# Experimento micro-LF / NetEm V0

Estado em 21/10/2026: NetEm validado e removido; toolchain instalado;
federação compilada; baseline válido com 100 mensagens normais e zero tardy.
**Campanha concluída e auditada: 20/20 runs C0–C3 válidos**, com cinco
repetições por cenário. Nenhuma intervenção manual permanece pendente.
Veja [REPORT.md](REPORT.md), [PILOT_REPORT.md](PILOT_REPORT.md),
[results.csv](results/processed/results.csv) e `logs/final_audit.json`.

| Cenário | Jitter configurado | Taxa tardy média | IC bootstrap 95% |
| --- | ---: | ---: | ---: |
| C0 | 0 ms | 2,0% | 0,8–3,6% |
| C1 | 5 ms | 8,2% | 5,4–10,6% |
| C2 | 10 ms | 23,2% | 19,8–28,8% |
| C3 | 15 ms | 30,4% | 29,4–31,4% |

Resultados desta campanha em WSL2/loopback, com maxwait 20 ms e atraso-base
configurado 10 ms. ICs exploratórios; tardy/STP não equivale a deadline miss.

## QUICK START

Para analisar a campanha existente, sem repetir nenhuma coleta, no Ubuntu/WSL:

```bash
cd /mnt/c/Users/55839/Desktop/microLF-jitter-experiment/experiment_v0_final
source config/toolchain.env
"$ANALYSIS_PYTHON" scripts/analyze.py --campaign v0_20261021T140846_final
python3 scripts/final_audit.py
```

`scripts/plot.py` reconstrói as figuras exclusivamente dos CSVs processados.
A análise completa já o executa. Para gerar somente os gráficos, use
`"$ANALYSIS_PYTHON" scripts/plot.py`. A auditoria não executa federados nem
altera o qdisc.

## Reprodução do zero em uma nova área

Preserve a campanha atual. Para criar outra área somente com entradas do
experimento (sem logs, observações, binários ou congelamento anteriores):

```bash
bash scripts/new_replication.sh "$HOME/microlf-v0-reproduction"
cd "$HOME/microlf-v0-reproduction"
# Pré-requisitos de um Ubuntu novo, se ainda não instalados:
sudo apt update
sudo apt install -y build-essential cmake git openjdk-17-jdk python3 curl unzip iproute2 kmod util-linux
bash scripts/setup_toolchain.sh
sudo -v
bash scripts/check_env.sh --netem-test
bash scripts/build.sh
bash scripts/run_one.sh B0 0 0 1 20261020 sanity implementation
bash scripts/campaign_terminal.sh
source config/toolchain.env
python3 scripts/final_audit.py
python3 scripts/write_report.py
python3 scripts/final_audit.py --manifest
```

Compare as versões das ferramentas e do kernel com as registradas no
relatório. O plano/seeds é reprodutível; as taxas medidas podem variar entre
execuções reais. Dados da nova campanha ficam separados da campanha original.

A auditoria salva `logs/environment.txt` e uma cópia com nome exclusivo. O
código de saída 1 sinaliza pré-requisitos ausentes, mesmo se a inspeção terminou.

Teste NetEm para um ambiente ainda não validado, no terminal Ubuntu:

```bash
sudo -v && bash scripts/check_env.sh --netem-test
```

Esse comando solicita a senha local pelo sudo, carrega `sch_netem`, aplica
10 ms no loopback, registra o qdisc e o remove imediatamente. Não informe
sua senha no chat. O teste recusa substituir um qdisc preexistente e usa traps
para limpeza em saída, erro, INT e TERM. Como em qualquer script, SIGKILL ou
falha da máquina não permitem executar traps.

**NetEm em `lo` pode afetar outros serviços locais e tráfego de controle.**
Não execute o teste durante atividade local que não possa sofrer interferência.

Limpeza de emergência, apenas se o qdisc do teste permanecer:

```bash
tc qdisc show dev lo
sudo tc qdisc del dev lo root handle 7e00:
tc qdisc show dev lo
```

Sucesso do NetEm não significa sucesso da auditoria inteira: o script ainda
pode retornar 1 por outro pré-requisito ausente. A inspeção simples, sem
alterar a rede, está disponível em `bash scripts/check_env.sh --inspect`.

Comandos individuais, disponíveis para uma nova campanha:

```bash
# Instalação reprodutível em outra máquina Linux:
bash scripts/setup_toolchain.sh
bash scripts/build.sh
# Teste de implementação sem NetEm:
bash scripts/run_one.sh B0 0 0 1 20261020 sanity baseline_nova
# Uma sessão autenticada cobre probe, piloto e final automaticamente:
bash scripts/campaign_terminal.sh
# Ou, no mesmo terminal autenticado, separadamente:
sudo -v
bash scripts/run_probe.sh
bash scripts/run_pilot.sh
bash scripts/run_all.sh
# Reconstrução do CSV, estatísticas e gráficos a partir dos logs:
source config/toolchain.env
"$ANALYSIS_PYTHON" scripts/analyze.py
# Testes de invalidez do analisador, fora de results/:
python3 scripts/test_analysis.py
```

O piloto usa uma repetição por cenário e para se todos forem ≤1% ou todos
≥99% tardy. Um piloto informativo grava `config/frozen.json`; a campanha
confere hashes da configuração, fonte e binários antes de cada run.
Os arquivos brutos são organizados por fase/campanha/run, com nomes exclusivos.
`results.csv` contém somente a campanha final selecionada; `all_runs.csv`
preserva também baseline, probe, piloto e runs inválidos.

O Receiver tem timer local de 50 ms para avançar o tempo lógico quando falta
o input remoto; ele não incrementa contadores. A instrumentação usa
CLOCK_MONOTONIC no mesmo Linux. `one_way_delay_ms` é envio→execução da reação
de entrada, incluindo runtime/agendamento, e não mede exclusivamente rede.
Clock sync está desligado; os processos compartilham `LF_CLOCK_EPOCH_NS`
conforme o runtime oficial. Tardy/STP não é deadline miss.

`config/experiment.env` contém os parâmetros iniciais; `requirements.txt`
fixa versões instaladas no Python 3.14.4 do WSL. O toolchain está em
`~/.local/share/microlf-jitter-v0/`, fora do projeto para evitar cópias de
dependências e builds no disco Windows. `config/toolchain.env` fixa o commit
e permite definir TOOLCHAIN_HOME em outra máquina. O backend native usa
diretamente o runtime oficial; nenhum template adicional foi necessário.
