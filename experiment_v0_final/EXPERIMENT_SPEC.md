# Especificação V0 — parâmetros iniciais

Pergunta: como o parâmetro de jitter da rede modifica a taxa de mensagens
tardy/STP com maxwait fixo e demais condições controladas?

Sender e Receiver serão federados reais, em processos distintos, com TCP no
mesmo Linux. Sintaxe e APIs dependerão do compilador micro-LF efetivamente
instalado. Não foi escrito código micro-LF sem essa verificação.

| Parâmetro | Valor inicial |
| --- | --- |
| Período | 50 ms |
| maxwait explícito no Receiver | 20 ms |
| Warm-up | seq 0–9, excluídos da métrica |
| Medição | seq 10–109, exatamente 100 mensagens |
| Grace period | 2 segundos |
| Atraso-base C0–C3 | 10 ms |
| Jitter configurado C0/C1/C2/C3 | 0/5/10/15 ms |
| Distribuição C1–C3 | normal |
| Repetições finais | 5 por cenário |
| Seed mestre e bootstrap | 20261020 |
| Reamostragens bootstrap | 10.000, sobre RUNS |

B0: ausência de NetEm, apenas sanity check. C0: `netem delay 10ms`.
C1–C3: `netem delay 10ms <jitter>ms distribution normal`.
Os valores de jitter não representam uma faixa ±, e o atraso-base configurado
não garante que a média observada seja 10 ms, especialmente sob truncamento,
TCP e tráfego de controle.

Validade: 100 envios medidos e 100 recebimentos medidos, com os identificadores
esperados presentes exatamente uma vez. Duplicatas, ausências e falhas de
processo invalidam o run. Taxa = 100 × tardy / 100, apenas em runs válidos.
Contar startup separadamente; timer local do Receiver não conta mensagens.

Ordem: blocos com permutação C0–C3 e seed mestre fixa, ordem persistida antes
da coleta; registrar seed NetEm quando suportada. Piloto separado dos dados
finais. Se todos os cenários saturarem perto de 0% ou 100%, parar e documentar
antes de qualquer calibração. Não prometer monotonicidade.

Jitter será induzido exclusivamente pela rede. Não usar sleep/delay/espera
ativa em reações. Tardy/STP não é deadline miss; maxwait não é deadline.

Critérios de aceite: toolchain identificado; build; baseline; prova do
handler tardy em teste separado; NetEm comprovado; piloto informativo; 20 runs
finais válidos; análise e gráficos reproduzíveis. Esta especificação não é
evidência de execução dessas etapas. O cumprimento dos critérios foi
posteriormente documentado em REPORT.md e logs/final_audit.json.

Detalhes de implementação fixados antes da campanha final: timer de
progressão local no Receiver de 50 ms, clock sync off, época física comum e
buffer da conexão de 110 mensagens. O buffer padrão foi corrigido após um
probe de implementação inválido, antes do piloto. Piloto: uma repetição por
cenário; saturação se todos ≤1% ou todos ≥99%; seed 20261021. Os parâmetros
do fator e maxwait não foram calibrados.
