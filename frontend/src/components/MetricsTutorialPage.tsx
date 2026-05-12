import type { Dashboard } from "../api/client";

export function MetricsTutorialPage({ data, onClose }: { data: Dashboard; onClose: () => void }) {
  const acwr = data.injury_risk.acwr;
  const acwr_zone = data.injury_risk.zone;
  const ot = data.overtraining;
  const pol = data.polarization;
  const cal = data.calories;
  const profile = data.profile;
  const tdee = cal.average.total;
  const bmi = profile.bmi;

  return (
    <div className="wrapped-overlay">
      <div className="wrapped-page" style={{ maxWidth: 900 }}>
        <div className="wrapped-head">
          <div>
            <span className="wrapped-tag">GUIA</span>
            <h1 style={{ margin: 0, fontSize: 36 }}>O que cada métrica significa</h1>
          </div>
          <button className="btn" onClick={onClose}>Fechar ✕</button>
        </div>

        <div className="muted" style={{ marginBottom: 24, fontSize: 13 }}>
          Cada bloco usa seus próprios números como exemplo — pra entender o que o dashboard está te mostrando.
        </div>

        <div className="tut-section">
          <h2 className="tut-title">🏋️ TRIMP — quanto carga teve um treino</h2>
          <p>
            <strong>TRIMP</strong> (TRaining IMPulse) é uma unidade que mede o esforço de um treino, multiplicando <em>duração</em> × <em>intensidade FC</em>.
            Z1 vale pouco (≈0.9 pts/min), Z5 vale muito (≈4.5 pts/min). Um treino de 1h em Z2 = ~90 pts; 1h em Z4 = ~210 pts.
            É a base pra calcular ACWR e prescrição.
          </p>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">📈 ACWR — risco de lesão</h2>
          <p>
            <strong>ACWR</strong> = carga aguda (média 7d) ÷ carga crônica (média 28d).
            Estudos (Gabbett 2016) mostram que <strong>1.5+</strong> = risco elevado de lesão; <strong>0.8-1.3</strong> = sweet spot.
            Seu ACWR atual: <strong>{acwr ?? "—"}</strong> (zona: <strong>{acwr_zone}</strong>).
          </p>
          <ul className="tut-list">
            <li>&lt; 0.8 — Destreino: carga baixa, perde adaptação</li>
            <li>0.8–1.3 — <strong>Ideal:</strong> progresso seguro</li>
            <li>1.3–1.5 — Cuidado: considere recuperação</li>
            <li>&gt; 1.5 — <strong>Alto risco</strong> de lesão</li>
          </ul>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">💗 HRV — variabilidade da frequência cardíaca</h2>
          <p>
            HRV mede a variação de tempo entre batimentos durante o sono. <strong>↑ HRV = mais recuperada</strong>. Quando cai
            abaixo do baseline, indica fadiga (do treino, sono ruim, estresse, doença).
            HRV médio seu período: <strong>{data.wellness.avg_hrv ?? "—"} ms</strong>.
          </p>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">😴 Overtraining detector — score 0-4</h2>
          <p>
            Combina 4 sinais (cada um vale 1 ponto):
          </p>
          <ul className="tut-list">
            <li>HRV últimos 3d abaixo do baseline</li>
            <li>FC repouso últimos 3d acima do normal +5 bpm</li>
            <li>3+ noites &lt; 6h na última semana</li>
            <li>3+ noites com sleep score &lt; 50 na última semana</li>
          </ul>
          <p>
            Score atual: <strong>{ot.score}/4</strong> ({ot.flag}). {ot.message}
          </p>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">📊 Polarização 80/20 nas zonas FC</h2>
          <p>
            Modelo polarizado (Seiler) recomenda <strong>~80% em Z1-Z2</strong> (base aeróbica) e <strong>~20% em Z4-Z5</strong> (qualidade),
            <strong> evitando Z3</strong> (zona cinza — cansa sem ganho proporcional).
          </p>
          <p>
            Seu agregado 28d:{" "}
            <strong>Z1-Z2 {pol.low_pct ?? "—"}%</strong> · <strong>Z3 {pol.mid_pct ?? "—"}%</strong> · <strong>Z4-Z5 {pol.high_pct ?? "—"}%</strong> — veredicto: <strong>{pol.verdict}</strong>.
          </p>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">🔥 BMR vs TDEE — calorias diárias</h2>
          <p>
            <strong>BMR</strong> (Basal Metabolic Rate) é o gasto em repouso pelas 24h (manutenção básica).
            <strong> TDEE</strong> (Total Daily Energy Expenditure) é BMR + tudo que você faz no dia (exercício, andar, digerir).
          </p>
          <p>
            Seu TDEE médio: <strong>{tdee?.toLocaleString("pt-BR") ?? "—"} kcal/dia</strong>.
            Pra <strong>manter peso</strong>, comer ~{tdee?.toLocaleString("pt-BR")} kcal. Déficit de 300-500 = perda; superávit similar = ganho.
          </p>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">📏 IMC — só uma referência grosseira</h2>
          <p>
            <strong>IMC</strong> = peso ÷ altura². Saudável: 18.5-25. Mas <strong>não distingue músculo de gordura</strong> —
            atletas musculosos têm IMC alto sem ser sobrepeso. Use como referência inicial, não como fim.
          </p>
          <p>
            Seu IMC: <strong>{bmi ?? "—"}</strong>.
          </p>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">🏃 Riegel — predição de tempo de prova</h2>
          <p>
            Fórmula clássica: <code>T₂ = T₁ × (D₂/D₁)<sup>1.06</sup></code>. Pega seu melhor tempo recente em uma distância e extrapola pra outra.
            Funciona bem para diferenças até 50% (ex: usar 5k pra prever 10k); pra maratona partindo de 5k já é arriscado.
          </p>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">🩺 Garmin FirstBeat — predição via VO2max</h2>
          <p>
            O relógio combina <strong>VO2max</strong> + suas zonas FC + histórico recente pra estimar tempo de prova.
            Em geral mais preciso que Riegel pra distâncias longas porque incorpora condicionamento aeróbico atual.
          </p>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">⏱️ Pace × velocidade × cadência</h2>
          <ul className="tut-list">
            <li><strong>Pace</strong> (min/km ou min/100m) — quanto tempo pra cobrir 1 unidade. ↓ é melhor.</li>
            <li><strong>Velocidade</strong> (km/h) — quantos km em 1h. ↑ é melhor. Bike usa essa.</li>
            <li><strong>Cadência</strong> — passos/min (corrida ~170-180), rpm (bike ~70-90), braçadas/min (nado ~25-35).</li>
          </ul>
        </div>

        <div className="tut-section">
          <h2 className="tut-title">🌊 Fases do treinamento</h2>
          <ul className="tut-list">
            <li><strong>Base</strong> (8+ semanas pré-prova) — volume aeróbico</li>
            <li><strong>Build</strong> (4-8 sem) — adiciona intensidade Z3/Z4</li>
            <li><strong>Peak</strong> (2-4 sem) — pico de carga, treinos específicos</li>
            <li><strong>Taper</strong> (1-2 sem) — reduz volume 30-40%, mantém intensidade</li>
            <li><strong>Race week</strong> — descanso ativo, hidratação, sono</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
