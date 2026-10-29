#!/usr/bin/env python3
"""
MÉTIS — Gerenciador e Validador de Achados Científicos (METIS-OPEN-001)
Ecossistema SisTer · Núcleo C++26
"""

import json
import sys
from pathlib import Path
from datetime import datetime

CATEGORIAS_VALIDAS = {
    "atualizacao_tecnica",
    "resultado_calculado",
    "hipotese",
    "simulacao",
    "achado_corroborado"
}

STATUS_VALIDOS = {"aprovado", "em_analise", "revisado"}

ROOT_DIR = Path(__file__).resolve().parent.parent
ACHADOS_FILE = ROOT_DIR / "web" / "api" / "public" / "achados.json"
NOTICIAS_FILE = ROOT_DIR / "web" / "api" / "public" / "noticias.json"
RESUMOS_FILE = ROOT_DIR / "web" / "api" / "public" / "resumos.json"


def validar_achados():
    if not ACHADOS_FILE.exists():
        print(f"ERRO: Arquivo {ACHADOS_FILE} não encontrado.", file=sys.stderr)
        return False

    with open(ACHADOS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    achados = data.get("achados", [])
    print(f"==> Validando {len(achados)} achados científicos cadastrados...")

    erros = 0
    ids_vistos = set()

    for idx, a in enumerate(achados):
        aid = a.get("id")
        if not aid:
            print(f"  [!] Achado #{idx}: campo 'id' ausente.", file=sys.stderr)
            erros += 1
        elif aid in ids_vistos:
            print(f"  [!] Achado #{idx}: id duplicado '{aid}'.", file=sys.stderr)
            erros += 1
        else:
            ids_vistos.add(aid)

        cat = a.get("categoria")
        if cat not in CATEGORIAS_VALIDAS:
            print(f"  [!] Achado {aid}: categoria '{cat}' inválida. Válidas: {CATEGORIAS_VALIDAS}", file=sys.stderr)
            erros += 1

        sit = a.get("situacao_validacao")
        if sit not in STATUS_VALIDOS:
            print(f"  [!] Achado {aid}: situação de validação '{sit}' inválida.", file=sys.stderr)
            erros += 1

        for obrigatorio in ["titulo", "resumo", "data", "modelo", "ano_referencia", "natureza_evidencia", "fontes"]:
            if not a.get(obrigatorio):
                print(f"  [!] Achado {aid}: campo obrigatório '{obrigatorio}' ausente ou vazio.", file=sys.stderr)
                erros += 1

    if erros == 0:
        print(f"✅ Todos os {len(achados)} achados estão conformes à diretriz METIS-OPEN-001.")
        return True
    else:
        print(f"❌ Encontrados {erros} erros de validação.", file=sys.stderr)
        return False


def registrar_achado(titulo, resumo, categoria, modelo, natureza, fontes, situacao="aprovado"):
    if categoria not in CATEGORIAS_VALIDAS:
        raise ValueError(f"Categoria '{categoria}' inválida. Use uma de: {CATEGORIAS_VALIDAS}")

    with open(ACHADOS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    seq = len(data.get("achados", [])) + 1
    novo_id = f"ACH-{datetime.now().year}-{seq:03d}"

    novo_achado = {
        "id": novo_id,
        "titulo": titulo,
        "resumo": resumo,
        "categoria": categoria,
        "data": datetime.now().strftime("%Y-%m-%d"),
        "municipio_ibge": None,
        "modelo": modelo,
        "ano_referencia": "2017",
        "trajetoria": "experimental",
        "natureza_evidencia": natureza,
        "fontes": fontes,
        "versao_metis": "0.1.0",
        "limitacoes": "Avaliação baseada no Censo Agropecuário 2017 agregado.",
        "situacao_validacao": situacao
    }

    data["achados"].insert(0, novo_achado)
    data["total"] = len(data["achados"])
    data["data_atualizacao"] = datetime.now().isoformat()

    with open(ACHADOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Achado {novo_id} registrado com sucesso em {ACHADOS_FILE}!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--validar":
        valido = validar_achados()
        sys.exit(0 if valido else 1)
    else:
        validar_achados()
