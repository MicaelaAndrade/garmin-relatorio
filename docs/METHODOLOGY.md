# Metodologia

## ACWR — Acute:Chronic Workload Ratio

### Origem
Tim Gabbett (sport scientist) popularizou em 2016 a métrica ACWR para prever risco de lesão em esportes coletivos. Validação em rugby, futebol, AFL, e adotada por CrossFit/triathlon.

### Cálculo
```
carga_dia = duração_min × fator_HR

fator_HR (TRIMP simplificado):
  HR < 120: 1.0
  HR < 140: 1.5
  HR < 160: 2.5
  HR < 175: 4.0
  HR ≥ 175: 6.0

aguda  = média(carga_dia, últimos 7 dias)
crônica = média(carga_dia, últimos 28 dias)
ACWR = aguda / crônica
```

### Interpretação

| ACWR | Risco lesão | O que fazer |
|------|------------|-------------|
| < 0.8 | Baixo (mas destreino) | OK se descanso planejado; senão retomar gradual |
| 0.8 – 1.3 | **Sweet spot** | Manter ou progredir 5–10% |
| 1.3 – 1.5 | Moderado | Considere 1 dia extra leve |
| **> 1.5** | **Alto** (risco 2–4× maior) | Reduzir volume na semana |

### Limitações
- Precisa **mínimo 28 dias** de histórico (até lá: dados insuficientes)
- TRIMP por HR é proxy, não substitui sRPE (Rated Perceived Exertion) self-report
- Não captura intensidade pontual (sprints, tempo runs)
- Discutido na literatura: Wang et al. (2020) questionam o valor preditivo absoluto

### Referências
- Gabbett TJ. *The training-injury prevention paradox: should athletes be training smarter and harder?* Br J Sports Med 2016.
- Hulin BT et al. *Spikes in acute workload are associated with increased injury risk in elite cricket fast bowlers.* BJSM 2014.

---

## Fórmula de Riegel

Pete Riegel (1981) propôs `T2 = T1 × (D2/D1)^1.06` para predizer tempo de prova em distância D2 a partir de tempo conhecido T1 em distância D1.

### Confiança
- ±20% da distância base: confiança **alta**
- ±20–50%: confiança **média**
- > 50%: confiança **baixa** (extrapolar de 5k pra maratona é arriscado)

### Limitações
- Assume preparo similar pra distância alvo. Se nunca correu mais de 10k, predição de 42k é otimista.
- Expoente 1.06 vale pra runners treinados; iniciantes têm decaimento maior (sugerido 1.07–1.08).
- Não considera elevação, calor, condição do dia.

---

## Readiness Score

Heurística simples sem pretensão de ser HRV-baseada como Whoop/Oura:

```
notes = []
sono_3d = média(sono_total_h, últimas 3 noites)
se sono_3d < 6.5: notes.append("sono curto")

baseline_RHR = média(resting_hr, dias 4 a 28 atrás)
recente_RHR = média(resting_hr, últimos 3 dias)
se recente_RHR > baseline_RHR + 5: notes.append("HR repouso elevado")

flag:
  0 notas → verde
  1 nota → amarelo
  2+ notas → vermelho
```

### Por que isso?
- Sono é o preditor #1 de recuperação (Walker, *Why We Sleep*, 2017).
- HR repouso elevado por 3+ dias indica fadiga sistêmica ou doença incipiente (Plews et al. 2013).

### O que falta (v2+)
- HRV trend (rMSSD ou SDNN overnight do Garmin)
- Stress score do Garmin
- Body battery médio
- Subjective wellness (1–10 self-report)
