#!/usr/bin/env python3
"""
MÉTIS — ETL Censo Agropecuário 2006 do IBGE via API SIDRA
Para os municípios do Rio Grande do Sul (UF 43).

Tabelas SIDRA consumidas:
- 1011: Uso das terras (Área total, pastagens naturais, matas/florestas naturais)
- 836: Valor da produção agropecuária (Mil R$ -> R$)
- 1016: Número total de estabelecimentos, estabelecimentos com orientação técnica e associados a cooperativas/entidades
"""

import urllib.request
import json
import gzip
import csv
import sys
import os
from typing import Dict, Any, Optional

HEADERS = {
    'User-Agent': 'ResilienciaRS-ETL/0.2.0 (pesquisa academica/territorial; contato@labeco)'
}

def fetch_json(url: str) -> Any:
    print(f"Baixando: {url}")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        if resp.info().get('Content-Encoding') == 'gzip' or raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        return json.loads(raw.decode('utf-8'))

def parse_sidra_val(s: Any) -> Optional[float]:
    if s is None:
        return None
    s = str(s).strip()
    if s in ('', 'NA', '..', '...', 'X'):
        return None
    if s == '-':
        return 0.0
    try:
        return float(s)
    except ValueError:
        return None

def main():
    os.makedirs('data/gerados', exist_ok=True)
    os.makedirs('data/raw', exist_ok=True)

    # 1. Tabela 1011: Uso das terras em 2006
    # Variavel 184 (Area dos estabelecimentos em ha)
    # 110087 = Total
    # 113472 = Pastagens - naturais
    # 113473 = Matas e/ou florestas - naturais APP / reserva legal
    # 113474 = Matas e/ou florestas - naturais outras
    url_1011 = (
        'https://servicodados.ibge.gov.br/api/v3/agregados/1011/periodos/2006/variaveis/184'
        '?localidades=N6[N3[43]]'
        '&classificacao=222[110087,113472,113473,113474]|12440[0]'
    )
    data_1011 = fetch_json(url_1011)

    # 2. Tabela 836: Valor da produção agropecuária em 2006
    # Variavel 1999 (Valor da producao em mil R$)
    url_836 = (
        'https://servicodados.ibge.gov.br/api/v3/agregados/836/periodos/2006/variaveis/1999'
        '?localidades=N6[N3[43]]'
        '&classificacao=12547[114017]|218[0]|12894[0]|12517[113601]|220[0]'
    )
    data_836 = fetch_json(url_836)

    # 3. Tabela 1016: Total de estabelecimentos, com orientação técnica e associados a cooperativas
    # Variavel 183 (Número de estabelecimentos)
    # Total de estabelecimentos: 12598[0]
    # Recebe orientação técnica: 12567[113111]
    # Associado a cooperativa/entidade: 12598[114543]
    url_1016 = (
        'https://servicodados.ibge.gov.br/api/v3/agregados/1016/periodos/2006/variaveis/183'
        '?localidades=N6[N3[43]]'
        '&classificacao=12559[0]|12557[0]|12553[0]|12598[0,114543]|12548[0]|12567[0,113111]'
    )
    data_1016 = fetch_json(url_1016)

    # Carregar a lista de 497 municípios oficiais de 2017/2022 para garantir o mesmo catálogo
    municipios_base = {}
    with open('data/gerados/municipios_rs_2017_homologado.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ibge = row['codigo_ibge'].strip()
            municipios_base[ibge] = row['municipio'].strip()

    # Dicionário estruturado para 2006
    municipios_2006 = {}
    for ibge, nome in municipios_base.items():
        municipios_2006[ibge] = {
            'codigo_ibge': ibge,
            'municipio': nome,
            'ano_referencia': 2006,
            'area_estabelecimentos_ha': None,
            'pastagem_natural_ha': None,
            'mata_natural_ha': None,
            'valor_producao_reais': None,
            'estabelecimentos_total': None,
            'estabelecimentos_orientacao_tecnica': None,
            'estabelecimentos_associados': None
        }

    # Processar Tabela 1011 (Terras 2006)
    matas_app_rl = {}
    matas_outras = {}

    for res in data_1011[0]['resultados']:
        cat_id = list(res['classificacoes'][0]['categoria'].keys())[0]
        for item in res['series']:
            ibge = item['localidade']['id']
            if ibge not in municipios_2006:
                continue
            val = parse_sidra_val(item['serie'].get('2006'))
            if cat_id == '110087': # Total
                municipios_2006[ibge]['area_estabelecimentos_ha'] = val
            elif cat_id == '113472': # Pastagem natural
                municipios_2006[ibge]['pastagem_natural_ha'] = val
            elif cat_id == '113473': # Matas APP/RL
                matas_app_rl[ibge] = val
            elif cat_id == '113474': # Matas outras
                matas_outras[ibge] = val

    # Consolidar matas naturais (APP/RL + outras)
    for ibge in municipios_2006:
        m_app = matas_app_rl.get(ibge)
        m_out = matas_outras.get(ibge)
        if m_app is not None and m_out is not None:
            municipios_2006[ibge]['mata_natural_ha'] = m_app + m_out
        elif m_app is not None:
            municipios_2006[ibge]['mata_natural_ha'] = m_app
        elif m_out is not None:
            municipios_2006[ibge]['mata_natural_ha'] = m_out

    # Processar Tabela 836 (Valor da Produção 2006 em mil R$)
    for res in data_836[0]['resultados']:
        for item in res['series']:
            ibge = item['localidade']['id']
            if ibge in municipios_2006:
                val = parse_sidra_val(item['serie'].get('2006'))
                if val is not None:
                    # Converter mil R$ para R$ correntes de 2006
                    municipios_2006[ibge]['valor_producao_reais'] = round(val * 1000.0, 2)

    # Processar Tabela 1016 (Estabelecimentos, Orientação Técnica e Cooperativismo)
    for res in data_1016[0]['resultados']:
        classifs = {c['id']: list(c['categoria'].keys())[0] for c in res['classificacoes']}
        cat_coop = classifs.get('12598')
        cat_ori = classifs.get('12567')

        is_total = (cat_coop == '0' and cat_ori == '0')
        is_orientacao = (cat_coop == '0' and cat_ori == '113111')
        is_associado = (cat_coop == '114543' and cat_ori == '0')

        for item in res['series']:
            ibge = item['localidade']['id']
            if ibge in municipios_2006:
                val = parse_sidra_val(item['serie'].get('2006'))
                if val is not None:
                    val_int = int(round(val))
                    if is_total:
                        municipios_2006[ibge]['estabelecimentos_total'] = val_int
                    elif is_orientacao:
                        municipios_2006[ibge]['estabelecimentos_orientacao_tecnica'] = val_int
                    elif is_associado:
                        municipios_2006[ibge]['estabelecimentos_associados'] = val_int

    # Salvar arquivo homologado de 2006
    saida_csv = 'data/gerados/municipios_rs_2006_homologado.csv'
    fieldnames = [
        'codigo_ibge', 'municipio', 'ano_referencia',
        'area_estabelecimentos_ha', 'pastagem_natural_ha', 'mata_natural_ha',
        'valor_producao_reais', 'estabelecimentos_total',
        'estabelecimentos_orientacao_tecnica', 'estabelecimentos_associados'
    ]

    with open(saida_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ibge in sorted(municipios_2006.keys()):
            r = municipios_2006[ibge]
            row_dict = {
                'codigo_ibge': r['codigo_ibge'],
                'municipio': r['municipio'],
                'ano_referencia': r['ano_referencia'],
                'area_estabelecimentos_ha': int(round(r['area_estabelecimentos_ha'])) if r['area_estabelecimentos_ha'] is not None else '',
                'pastagem_natural_ha': int(round(r['pastagem_natural_ha'])) if r['pastagem_natural_ha'] is not None else '',
                'mata_natural_ha': int(round(r['mata_natural_ha'])) if r['mata_natural_ha'] is not None else '',
                'valor_producao_reais': int(round(r['valor_producao_reais'])) if r['valor_producao_reais'] is not None else '',
                'estabelecimentos_total': r['estabelecimentos_total'] if r['estabelecimentos_total'] is not None else '',
                'estabelecimentos_orientacao_tecnica': r['estabelecimentos_orientacao_tecnica'] if r['estabelecimentos_orientacao_tecnica'] is not None else '',
                'estabelecimentos_associados': r['estabelecimentos_associados'] if r['estabelecimentos_associados'] is not None else ''
            }
            writer.writerow(row_dict)

    print(f"\n[SUCESSO] Dados do Censo 2006 homologados e salvos em: {saida_csv}")
    print(f"Total de municípios processados: {len(municipios_2006)}")

if __name__ == '__main__':
    main()
