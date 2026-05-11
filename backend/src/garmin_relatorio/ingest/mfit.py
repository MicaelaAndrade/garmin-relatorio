"""Parser de PDF do MFit Personal (treinos de fortalecimento).

Importa rotinas (Full body 1, Full body 2, etc) e exercicios (nome, series,
carga, intervalo, instrucoes) a partir do PDF gerado pelo app MFit.

Mapeamento default dos dias da semana:
- Rotina 1 -> Segunda (weekday=0)
- Rotina 2 -> Sexta (weekday=4)
Pode ser sobrescrito via parametro/cli.
"""
from __future__ import annotations

import logging
import re
import urllib.request
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from ..config import ROOT
from ..db import connect

log = logging.getLogger(__name__)


DEFAULT_WEEKDAY_BY_ORDER = {1: 0, 2: 4}  # Seg, Sex

# Linhas que marcam inicio de uma rotina. Captura titulos como "Full body 1", "AB1", "Peito e ombro" etc.
# Heuristica: rotina = secao que aparece sozinha em uma linha e nao matches abaixo.
EXERCISE_FIELD_RE = re.compile(r"^\s*(S[ée]ries|Carga|Intervalo|Instru[çc][õo]es)\s*[:.]", re.IGNORECASE)
ROUTINE_HEADER_RE = re.compile(
    r"^(?:Full\s*body\s*\d+|AB\s*\d+|ABC\s*\d+|Treino\s+[A-EI-IV0-9]+|Rotina\s+\w+)\s*$",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    """Remove caracteres invisíveis e icones (Private Use Area)."""
    # pypdf preserva icones do PDF como caracteres Unicode Private Use Area (U+E000-U+F8FF).
    # Esses caracteres atrapalham o regex de campo (ex: " Intervalo: 20s").
    out_chars = []
    for ch in text:
        cp = ord(ch)
        if 0xE000 <= cp <= 0xF8FF:
            continue  # icone do app, descarta
        if cp == 0xA0 or cp == 0xC2:
            out_chars.append(" ")
            continue
        out_chars.append(ch)
    return "".join(out_chars).replace("\r", "")


def _parse_rest(raw: str) -> tuple[int | None, str | None]:
    """'Intervalo: 60s' -> (60, '60s'). 'Intervalo: 1m 30s' -> (90, '1m 30s')."""
    if not raw:
        return None, None
    raw = raw.strip()
    m = re.search(r"(\d+)\s*m\s*(\d+)\s*s?", raw)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)), raw
    m = re.search(r"(\d+)\s*m\b", raw)
    if m:
        return int(m.group(1)) * 60, raw
    m = re.search(r"(\d+)\s*s\b", raw)
    if m:
        return int(m.group(1)), raw
    m = re.search(r"^\d+$", raw)
    if m:
        return int(raw), raw
    return None, raw


def _parse_load(raw: str) -> tuple[float | None, str]:
    """'20kg' -> (20.0, '20kg'). 'nenhuma' -> (None, 'nenhuma')."""
    if not raw:
        return None, ""
    raw = raw.strip()
    if "nenhum" in raw.lower():
        return None, raw
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*kg", raw, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ".")), raw
    m = re.search(r"^(\d+(?:[.,]\d+)?)$", raw)
    if m:
        return float(m.group(1).replace(",", ".")), raw
    return None, raw


def _split_into_routines(text: str) -> list[dict[str, Any]]:
    """Divide texto bruto em rotinas e exercicios.

    Algoritmo:
    1. Quebra por linhas tipo 'Full body N' -> N rotinas.
    2. Em cada rotina, identifica blocos delimitados por 'Séries:'. O conteudo
       ANTES de 'Séries:' (ate o ultimo bloco fechado) e' o nome do exercicio
       atual; o conteudo entre 'Séries:' e o proximo 'Séries:' contem os campos.
    3. Nome e' as 1-3 ultimas linhas nao-campo, nao-instrucao acima de 'Séries:'.
    """
    raw_lines = [ln.rstrip() for ln in _normalize(text).split("\n")]
    # Segmenta por rotina
    routine_starts: list[tuple[int, str]] = []
    for i, ln in enumerate(raw_lines):
        if ROUTINE_HEADER_RE.match(ln.strip()):
            routine_starts.append((i, ln.strip()))

    if not routine_starts:
        # Sem header reconhecido: trata o documento inteiro como 1 rotina sem nome
        routine_starts = [(0, "Rotina 1")]

    # Adiciona sentinela final
    bounds = [(s[0], s[1], routine_starts[i + 1][0] if i + 1 < len(routine_starts) else len(raw_lines))
              for i, s in enumerate(routine_starts)]

    routines: list[dict] = []
    for order_idx, (start, name, end) in enumerate(bounds, start=1):
        section_lines = raw_lines[start + 1:end]
        exercises = _parse_exercise_blocks(section_lines)
        routines.append({
            "name": name,
            "order_idx": order_idx,
            "exercises": exercises,
        })
    return routines


def _parse_exercise_blocks(lines: list[str]) -> list[dict[str, Any]]:
    """Parser por blocos: encontra cada 'Séries:' e monta o exercicio."""
    # Pre-classifica cada linha
    classified: list[tuple[str, str]] = []  # (kind, value)
    for raw in lines:
        line = raw.strip()
        if not line:
            classified.append(("blank", ""))
            continue
        m = EXERCISE_FIELD_RE.match(line)
        if m:
            field = m.group(1).lower()
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            if field.startswith("s") and "rie" in field:
                classified.append(("series", value))
            elif field == "carga":
                classified.append(("carga", value))
            elif field.startswith("interv"):
                classified.append(("intervalo", value))
            elif field.startswith("instru"):
                classified.append(("instrucoes_marker", value))
            else:
                classified.append(("text", line))
        else:
            classified.append(("text", line))

    # Itera identificando blocos de exercicio. Estado: pre-name, in-fields, in-instructions
    exercises: list[dict] = []
    name_buffer: list[str] = []
    current: dict | None = None
    in_instructions = False

    def _commit() -> None:
        nonlocal current, in_instructions
        if current is not None:
            if current["instructions"]:
                current["instructions"] = current["instructions"].strip()
            exercises.append(current)
        current = None
        in_instructions = False

    for kind, value in classified:
        if kind == "series":
            # Heuristica: se exercicio anterior tem instrucoes, a ultima linha pode ser
            # o nome do PROXIMO exercicio (sem separador no PDF)
            pending_from_instr = _extract_trailing_name(current)
            _commit()
            name = pending_from_instr or _build_name(name_buffer)
            name_buffer = []
            current = {
                "name": name,
                "sets": value,
                "load_text": "",
                "load_kg": None,
                "rest_s": None,
                "rest_text": None,
                "instructions": "",
                "order_idx": len(exercises) + 1,
            }
            in_instructions = False
            continue
        if current is None:
            # Antes do primeiro exercicio: acumula nome
            if kind == "text":
                name_buffer.append(value)
            continue
        if kind == "carga":
            load_kg, load_text = _parse_load(value)
            current["load_kg"] = load_kg
            current["load_text"] = load_text
            in_instructions = False
            continue
        if kind == "intervalo":
            rest_s, rest_text = _parse_rest(value)
            current["rest_s"] = rest_s
            current["rest_text"] = rest_text
            in_instructions = False
            continue
        if kind == "instrucoes_marker":
            in_instructions = True
            continue
        if kind == "text":
            if in_instructions:
                # Preserva quebra de linha pra permitir extracao da ultima linha como nome
                if current["instructions"]:
                    current["instructions"] += "\n"
                current["instructions"] += value
            else:
                name_buffer.append(value)
            continue
        if kind == "blank":
            # Linha em branco fecha bloco de instrucoes; nao corta nome buffer
            in_instructions = False
            continue

    _commit()
    return exercises


def _extract_trailing_name(exercise: dict | None) -> str:
    """Se as instrucoes terminam com uma linha que parece nome de exercicio,
    retira essa linha e devolve como nome. Heuristica:
    - <50 chars
    - nao termina com pontuacao (. , ; :)
    - primeira letra maiuscula
    - opcionalmente: tem ao menos 1 palavra com >=2 letras
    """
    if not exercise or not exercise.get("instructions"):
        return ""
    parts = exercise["instructions"].split("\n")
    # Acumula nome a partir do final enquanto encontrar linhas curtas sem pontuacao
    name_lines: list[str] = []
    while parts:
        last = parts[-1].strip()
        if not last:
            parts.pop()
            continue
        if len(last) > 60:
            break
        if last[-1] in ".,:;?!":
            break
        if not last[0].isalpha():
            break
        # Para nomes em CAIXA ALTA ou Title Case
        first_char = last[0]
        if not (first_char.isupper() or last.startswith(("Abdominal", "Supino", "Remada", "Cadeira", "Agachamento", "Bom Dia", "Tríceps", "Triceps", "Rosca", "Elevação", "Manobra", "Panturrilha", "Puxada"))):
            break
        name_lines.insert(0, last)
        parts.pop()
        # Suporta nome em 2 linhas: ex "ELEVAÇÃO PÉLVICA SUMÔ NO\nBANCO"
        if len(name_lines) >= 2:
            break
    if not name_lines:
        return ""
    exercise["instructions"] = "\n".join(parts).strip()
    return " ".join(name_lines).strip()


def _build_name(buffer: list[str]) -> str:
    """Pega as ultimas 1-3 linhas do buffer como nome do exercicio.

    Heuristica: nome tipico tem 1-3 linhas, comeca com letra maiuscula. Se buffer
    tem N linhas, pega as ultimas 3 enquanto a primeira nao tem mais que ~5 palavras
    e ainda parece nome (nao instrucao residual).
    """
    if not buffer:
        return ""
    # Heuristica: agarra ate 3 ultimas linhas que juntas formam <= 80 chars
    out: list[str] = []
    total = 0
    for ln in reversed(buffer):
        if total + len(ln) > 80 and out:
            break
        out.insert(0, ln)
        total += len(ln)
        if len(out) >= 3:
            break
    return " ".join(out).strip()


def parse_pdf(pdf_path: Path) -> dict[str, Any]:
    """Le PDF do MFit e retorna estrutura {athlete, label, routines}."""
    reader = PdfReader(str(pdf_path))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    text = _normalize(text)

    # Tenta extrair atleta + label do header (primeiras 5 linhas)
    head = text.split("\n", 10)
    athlete = head[0].strip().replace(" " * 1, "") if head else ""
    # Junta linhas que comecam com "Rotina:" ou "Condicionamento"
    label = ""
    for ln in head[:6]:
        if "Rotina" in ln:
            label = ln.split(":", 1)[-1].strip()
            break
    level = ""
    for ln in head[:8]:
        if "ntermedi" in ln or "vançado" in ln or "niciante" in ln:
            level = ln.strip()
            break

    routines = _split_into_routines(text)
    return {
        "athlete": athlete,
        "label": label,
        "level": level,
        "routines": routines,
    }


def ingest_pdf(pdf_path: str | Path, weekday_map: dict[int, int] | None = None) -> dict[str, int]:
    """Importa rotinas do PDF MFit pro banco.

    weekday_map: dict {order_idx: weekday}. Default {1:0 (Seg), 2:4 (Sex)}.
    """
    path = Path(pdf_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"PDF nao encontrado: {path}")

    parsed = parse_pdf(path)
    wmap = weekday_map or DEFAULT_WEEKDAY_BY_ORDER

    source_file = path.name
    routines_inserted = 0
    exercises_inserted = 0

    with connect() as conn:
        # Limpa importacao anterior do MESMO arquivo (re-import idempotente)
        conn.execute("DELETE FROM strength_routines WHERE source_file = ?", (source_file,))

        for routine in parsed["routines"]:
            cur = conn.execute(
                """
                INSERT INTO strength_routines
                (source, source_file, name, order_idx, weekday, routine_label, fitness_level)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    "mfit",
                    source_file,
                    routine["name"],
                    routine["order_idx"],
                    wmap.get(routine["order_idx"]),
                    parsed.get("label"),
                    parsed.get("level"),
                ),
            )
            routine_id = cur.lastrowid
            routines_inserted += 1
            for ex in routine["exercises"]:
                if not ex.get("name"):
                    continue
                conn.execute(
                    """
                    INSERT INTO strength_exercises
                    (routine_id, order_idx, name, sets, load_text, load_kg, rest_s, rest_text, instructions)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        routine_id,
                        ex["order_idx"],
                        ex["name"],
                        ex.get("sets"),
                        ex.get("load_text"),
                        ex.get("load_kg"),
                        ex.get("rest_s"),
                        ex.get("rest_text"),
                        ex.get("instructions") or None,
                    ),
                )
                exercises_inserted += 1

    log.info(
        "MFit ingerido: %d rotinas, %d exercicios (%s)",
        routines_inserted, exercises_inserted, source_file,
    )
    return {"routines": routines_inserted, "exercises": exercises_inserted}


def ingest_url(url: str, weekday_map: dict[int, int] | None = None) -> dict[str, int]:
    """Baixa PDF de URL e ingere. Util pra links secureupload.mfitpersonal.com.br."""
    dest_dir = ROOT / "backend" / "data" / "mfit"
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Nome do arquivo: usa o ultimo segmento do path, default workout.pdf
    name = url.rstrip("/").split("/")[-1] or "workout.pdf"
    if not name.endswith(".pdf"):
        name += ".pdf"
    dest = dest_dir / name
    log.info("Baixando MFit PDF: %s -> %s", url, dest)
    urllib.request.urlretrieve(url, dest)  # noqa: S310 — URL confiavel fornecida pelo dev
    return ingest_pdf(dest, weekday_map=weekday_map)
