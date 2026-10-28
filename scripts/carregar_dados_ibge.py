#!/usr/bin/env python3
"""
ETL para carregar dados oficiais do Censo Agropecuário 2017 do IBGE via API SIDRA
para os 497 municípios do Rio Grande do Sul (UF 43).

Tabelas SIDRA consumidas:
- 6881: Área dos estabelecimentos, pastagem natural, matas e florestas naturais
- 6898: Valor da produção agropecuária (Mil R$ -> R$)
- 6780: Número total de estabelecimentos e com orientação técnica
- 6773: Estabelecimentos com produtor associado a cooperativa/entidade
"""

import urllib.request
import json
import gzip
import csv
import sys
import os

HEADERS = {
    'User-Agent': 'ResilienciaRS-ETL/0.1.0 (pesquisa academica/territorial; contato@labeco)'
}

def fetch_json(url):
    print(f"Baixando: {url}")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        if resp.info().get('Content-Encoding') == 'gzip' or raw[:2] == b'\x1f\x8b':
            raw = gzip.decompress(raw)
        return json.loads(raw.decode('utf-8'))

def parse_sidra_val(s):
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

    # 1. Tabela 6881: Uso das terras (Área total, pastagens naturais, matas naturais)
    # Variavel 184 (Area dos estabelecimentos em ha)
    # 110087 = Total
    # 113472 = Pastagens - naturais
    # 40679 = Matas/florestas naturais APP/RL
    # 40680 = Matas/florestas naturais outras
    url_6881 = (
        'https://servicodados.ibge.gov.br/api/v3/agregados/6881/periodos/2017/variaveis/184'
        '?localidades=N6[N3[43]]'
        '&classificacao=222[110087,113472,40679,40680]|829[46302]|218[46502]|12517[113601]|12567[41151]'
    )
    data_6881 = fetch_json(url_6881)
    
    # 2. Tabela 6898: Valor da produção agropecuária
    # Variavel 1999 (Valor da producao em mil R$)
    # Totais em todas as classificações
    url_6898 = (
        'https://servicodados.ibge.gov.br/api/v3/agregados/6898/periodos/2017/variaveis/1999'
        '?localidades=N6[N3[43]]'
        '&classificacao=12547[114017]|12894[46569]|220[110085]|829[46302]'
    )
    data_6898 = fetch_json(url_6898)

    # 3. Tabela 6780: Estabelecimentos total e orientação técnica
    # Variavel 183
    # 41151 = Total
    # 113111 = Recebe orientação técnica
    url_6780 = (
        'https://servicodados.ibge.gov.br/api/v3/agregados/6780/periodos/2017/variaveis/183'
        '?localidades=N6[N3[43]]'
        '&classificacao=12567[41151,113111]|829[46302]|12517[113601]|220[110085]'
    )
    data_6780 = fetch_json(url_6780)

    # 4. Tabela 6773: Associação a cooperativa/entidade de classe
    # Variavel 183
    # 114543 = É associado
    url_6773 = (
        'https://servicodados.ibge.gov.br/api/v3/agregados/6773/periodos/2017/variaveis/183'
        '?localidades=N6[N3[43]]'
        '&classificacao=12598[114543]|829[46302]|12559[41148]|12553[46523]|834[46527]|835[46528]'
    )
    data_6773 = fetch_json(url_6773)

    municipios = {}

    # Processar 6881
    for res in data_6881[0]['resultados']:
        cat_id = list(res['classificacoes'][0]['categoria'].keys())[0]
        for item in res['series']:
            ibge = item['localidade']['id']
            nome = item['localidade']['nome'].replace(' - RS', '').strip()
            if ibge not in municipios:
                municipios[ibge] = {
                    'codigo_ibge': ibge,
                    'municipio': nome,
                    'ano_referencia': '2017',
                    'area_total': None,
                    'pastagem_natural': None,
                    'mata_app_rl': None,
                    'mata_outra': None,
                    'valor_producao_mil': None,
                    'estab_total': None,
                    'estab_orientacao': None,
                    'estab_associado': None
                }
            val = parse_sidra_val(item['serie'].get('2017'))
            if cat_id == '110087':
                municipios[ibge]['area_total'] = val
            elif cat_id == '113472':
                municipios[ibge]['pastagem_natural'] = val
            elif cat_id == '40679':
                municipios[ibge]['mata_app_rl'] = val
            elif cat_id == '40680':
                municipios[ibge]['mata_outra'] = val

    # Processar 6898
    for item in data_6898[0]['resultados'][0]['series']:
        ibge = item['localidade']['id']
        if ibge in municipios:
            val = parse_sidra_val(item['serie'].get('2017'))
            municipios[ibge]['valor_producao_mil'] = val

    # Processar 6780
    for res in data_6780[0]['resultados']:
        cat_id = list(res['classificacoes'][0]['categoria'].keys())[0]
        for item in res['series']:
            ibge = item['localidade']['id']
            if ibge in municipios:
                val = parse_sidra_val(item['serie'].get('2017'))
                if cat_id == '41151':
                    municipios[ibge]['estab_total'] = val
                elif cat_id == '113111':
                    municipios[ibge]['estab_orientacao'] = val

    # Processar 6773
    for item in data_6773[0]['resultados'][0]['series']:
        ibge = item['localidade']['id']
        if ibge in municipios:
            val = parse_sidra_val(item['serie'].get('2017'))
            municipios[ibge]['estab_associado'] = val

    print(f"Total de municípios mapeados: {len(municipios)}")

    # Gerar CSV harmonizado oficial
    csv_path = 'data/gerados/municipios_rs_2017_homologado.csv'
    fieldnames = [
        'codigo_ibge',
        'municipio',
        'ano_referencia',
        'area_estabelecimentos_ha',
        'pastagem_natural_ha',
        'mata_natural_ha',
        'valor_producao_reais',
        'estabelecimentos_total',
        'estabelecimentos_orientacao_tecnica',
        'estabelecimentos_associados'
    ]

    def fmt_num(v):
        if v is None:
            return ""
        return f"{v:.4f}" if isinstance(v, float) and not v.is_integer() else f"{int(v)}"

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for ibge in sorted(municipios.keys()):
            m = municipios[ibge]
            
            # Matas e florestas naturais é a soma de APP/RL + outras matas naturais
            mata_total = None
            if m['mata_app_rl'] is not None or m['mata_outra'] is not None:
                mata_total = (m['mata_app_rl'] or 0.0) + (m['mata_outra'] or 0.0)

            # Valor da produção: em Mil Reais -> multiplicar por 1000 para Reais
            vp_reais = None
            if m['valor_producao_mil'] is not None:
                vp_reais = m['valor_producao_mil'] * 1000.0

            row = {
                'codigo_ibge': m['codigo_ibge'],
                'municipio': m['municipio'],
                'ano_referencia': '2017',
                'area_estabelecimentos_ha': fmt_num(m['area_total']),
                'pastagem_natural_ha': fmt_num(m['pastagem_natural']),
                'mata_natural_ha': fmt_num(mata_total),
                'valor_producao_reais': fmt_num(vp_reais),
                'estabelecimentos_total': fmt_num(m['estab_total']),
                'estabelecimentos_orientacao_tecnica': fmt_num(m['estab_orientacao']),
                'estabelecimentos_associados': fmt_num(m['estab_associado']),
            }
            writer.writerow(row)

    print(f"Arquivo CSV gravado com sucesso: {csv_path}")

if __name__ == '__main__':
    main()
