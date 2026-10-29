#include "resiliencia/model.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace resiliencia;

static void check(bool b, const std::string& msg) {
    if(!b) throw std::runtime_error("Teste falhou: " + msg);
}

int main() {
    try {
        // 1. Equação de estado R = E * (P + S)
        check(std::abs(estado(0.7, 35, 30) - 45.5) < 1e-9, "amortecimento E<1");
        check(std::abs(estado(1.0, 35, 30) - 65.0) < 1e-9, "neutralidade E=1");
        check(std::abs(estado(1.3, 35, 30) - 84.5) < 1e-9, "amplificacao E>1");
        
        bool failure = false;
        try { (void)estado(0, 1, 2); } catch(...) { failure = true; }
        check(failure, "E=0 invalido (E deve ser estritamente positivo)");

        // 2. Parametrização independente de P: P(k) = 50 * dm / (dm + k)
        ParametrosExperimento params{MODELO_EXP_004};
        params.k_produtiva = 1500.0;
        
        // Quando dm = 0 => P = 0
        RawMunicipio m_zero{"TEST-ZERO", "ZeroProd", "2017", 1000, 300, 200, 0, 100, 40, 40};
        auto n_zero = pontuar(m_zero, params);
        check(n_zero.status == "experimental", "status experimental para zero");
        check(std::abs(*n_zero.densidade_monetaria_ha - 0.0) < 1e-12, "dm = 0");
        check(std::abs(*n_zero.produtiva - 0.0) < 1e-12, "P = 0 quando dm = 0");

        // Quando dm = k (1500 R$/ha) => P = 25.0 (exatamente meio da escala)
        RawMunicipio m_k{"TEST-K", "PontoMedio", "2017", 100, 30, 20, 150000, 50, 20, 20}; // VP/A = 150000/100 = 1500 R$/ha
        auto n_k = pontuar(m_k, params);
        check(std::abs(*n_k.densidade_monetaria_ha - 1500.0) < 1e-12, "dm == k");
        check(std::abs(*n_k.produtiva - 25.0) < 1e-12, "P == 25 quando dm == k");

        // 3. INVARIANTE METODOLÓGICA FUNDAMENTAL (Critério 1 do METIS-DIR-MUN-001):
        // "A alteração dos dados de outro município não poderá modificar o resultado calculado para o município em análise"
        RawMunicipio munA{"4300001", "Municipio A", "2017", 50000, 20000, 10000, 75000000, 500, 200, 150};
        auto notaA_isolado = pontuar(munA, params);

        // Simulamos uma lista de outros municípios com dados heterogêneos e variantes
        std::vector<RawMunicipio> universo_cenario_1 = {
            munA,
            {"4300002", "Municipio B1", "2017", 10000, 5000, 1000, 10000000, 100, 30, 40},
            {"4300003", "Municipio C1", "2017", 200000, 150000, 20000, 500000000, 2000, 800, 1200}
        };
        auto notaA_cenario_1 = pontuar(universo_cenario_1[0], params);

        // Alteramos drasticamente os municípios B e C (mudança de valores em 1000x)
        std::vector<RawMunicipio> universo_cenario_2 = {
            munA,
            {"4300002", "Municipio B_Alterado", "2017", 999999, 10, 10, 999999999, 10, 1, 1},
            {"4300003", "Municipio C_Alterado", "2017", 500, 10, 10, 100, 5, 0, 0}
        };
        auto notaA_cenario_2 = pontuar(universo_cenario_2[0], params);

        check(std::abs(*notaA_isolado.resiliencia - *notaA_cenario_1.resiliencia) < 1e-15, "Invariancia Cenario 1");
        check(std::abs(*notaA_isolado.resiliencia - *notaA_cenario_2.resiliencia) < 1e-15, "Invariancia Cenario 2");
        check(std::abs(*notaA_isolado.produtiva - *notaA_cenario_2.produtiva) < 1e-15, "Invariancia P Cenario 2");
        check(std::abs(*notaA_isolado.ecologica - *notaA_cenario_2.ecologica) < 1e-15, "Invariancia E Cenario 2");
        check(std::abs(*notaA_isolado.social - *notaA_cenario_2.social) < 1e-15, "Invariancia S Cenario 2");

        // 4. Parâmetro inválido (k <= 0) deve ser rejeitado
        bool rejeitou_k_invalido = false;
        try {
            ParametrosExperimento p_inv{MODELO_EXP_004};
            p_inv.k_produtiva = 0.0;
            pontuar(munA, p_inv);
        } catch(const std::invalid_argument&) {
            rejeitou_k_invalido = true;
        }
        check(rejeitou_k_invalido, "Rejeicao de k <= 0");

        // 5. Inconsistência e dados incompletos
        RawMunicipio mun_inconsistente = munA;
        mun_inconsistente.com_orientacao = 600; // mais que estabelecimentos (500)
        check(pontuar(mun_inconsistente, params).status == "inconsistencia", "Deteccao de inconsistencia");

        RawMunicipio mun_incompleto = munA;
        mun_incompleto.valor_producao_reais = std::nullopt; // dado ausente
        auto nota_inc = pontuar(mun_incompleto, params);
        check(nota_inc.status == "dados_incompletos", "Deteccao de dados incompletos");
        check(!nota_inc.produtiva.has_value(), "Dado ausente nao vira zero em P");
        check(!nota_inc.resiliencia.has_value(), "Dado ausente nao vira zero em R");

        // 6. Testes do Catálogo Multimodelo (METIS-DIR-MULTI-002)
        ParametrosExperimento p_ref{MODELO_REF_001};
        auto n_ref = pontuar(munA, p_ref);
        check(n_ref.modelo == MODELO_REF_001, "modelo REF-001 identificado");
        check(n_ref.resiliencia.has_value() && *n_ref.resiliencia > 0, "R valido em REF-001");

        ParametrosExperimento p_aditivo{MODELO_EXP_002};
        p_aditivo.we = 0.33; p_aditivo.wp = 0.33; p_aditivo.ws = 0.34;
        auto n_aditivo = pontuar(munA, p_aditivo);
        check(n_aditivo.modelo == MODELO_EXP_002, "modelo EXP-002 identificado");
        check(n_aditivo.resiliencia.has_value() && *n_aditivo.resiliencia > 0, "R valido em EXP-002");

        ParametrosExperimento p_interativo{MODELO_EXP_003};
        p_interativo.lambda_interativo = 0.5;
        auto n_interativo = pontuar(munA, p_interativo);
        check(n_interativo.modelo == MODELO_EXP_003, "modelo EXP-003 identificado");
        check(*n_interativo.resiliencia > *notaA_isolado.resiliencia, "EXP-003 acopla sinergia positiva");

        // Confronto multimodelo para o município
        auto confronto = confrontar_modelos(munA, params);
        check(confronto.size() == 4, "confronto retorna exatamente 4 modelos do catalogo");
        check(confronto[0].modelo == MODELO_REF_001, "confronto[0] e REF-001");
        check(confronto[1].modelo == MODELO_EXP_002, "confronto[1] e EXP-002");
        check(confronto[2].modelo == MODELO_EXP_003, "confronto[2] e EXP-003");
        check(confronto[3].modelo == MODELO_EXP_004, "confronto[3] e EXP-004");

        std::cout << "✓ Todos os 15 testes de invariancia, modelagem municipal e catalogo multimodelo aprovados com sucesso.\n";
        return 0;
    } catch(const std::exception& e) {
        std::cerr << "ERRO: " << e.what() << "\n";
        return 1;
    }
}
