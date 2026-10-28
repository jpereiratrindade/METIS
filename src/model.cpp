#include "resiliencia/model.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace resiliencia {
namespace {
bool ok(const std::optional<double>& x) { return x && std::isfinite(*x) && *x >= 0; }
double clip(double x, double lo, double hi) { return std::clamp(x, lo, hi); }
}

double estado(double E, double P, double S) {
    if (!(std::isfinite(E) && std::isfinite(P) && std::isfinite(S) && E > 0 && P >= 0 && S >= 0))
        throw std::invalid_argument("Estado invalido: E>0, P>=0, S>=0");
    return E * (P + S);
}

std::optional<double> densidade_monetaria(const RawMunicipio& m) {
    if (!(ok(m.area_ha) && *m.area_ha > 0 && ok(m.valor_producao_reais))) return {};
    return *m.valor_producao_reais / *m.area_ha;
}

Nota pontuar(const RawMunicipio& m, const ParametrosExperimento& params) {
    Nota n{m.codigo, m.nome, m.referencia, "dados_incompletos", params.modelo, {}, {}, {}, {}, {}, {}, params.k_produtiva};
    if (params.k_produtiva <= 0 || !std::isfinite(params.k_produtiva)) {
        throw std::invalid_argument("Parametro k_produtiva deve ser estritamente positivo");
    }

    if (!(ok(m.area_ha) && *m.area_ha > 0 && ok(m.pastagem_natural_ha) && ok(m.mata_natural_ha)
        && ok(m.valor_producao_reais) && ok(m.estabelecimentos) && *m.estabelecimentos > 0
        && ok(m.com_orientacao) && ok(m.associados))) return n;

    if (*m.pastagem_natural_ha + *m.mata_natural_ha > *m.area_ha + 1e-7
        || *m.com_orientacao > *m.estabelecimentos || *m.associados > *m.estabelecimentos) {
        n.status = "inconsistencia";
        return n;
    }

    const double e0 = clip((*m.pastagem_natural_ha + *m.mata_natural_ha) / *m.area_ha, 0, 1);
    const double dm = *m.valor_producao_reais / *m.area_ha;
    const double soc_base = (*m.com_orientacao + *m.associados) / *m.estabelecimentos;

    n.densidade_monetaria_ha = dm;
    n.ecol_indice = e0;

    if (params.modelo == MODELO_REF_001) {
        // EPS-REF-001 (Referencia historica E-P-S com percentis q10 e q90)
        const double E = 0.5 + e0;
        const double L = std::log1p(dm);
        const double P = (params.q90 > params.q10) ? 50.0 * clip((L - params.q10) / (params.q90 - params.q10), 0, 1) : 0.0;
        const double S = 25.0 * soc_base;
        n.ecologica = E;
        n.produtiva = P;
        n.social = S;
        n.resiliencia = estado(E, P, S);
    } else if (params.modelo == MODELO_EXP_002) {
        // EPS-EXP-002 (Aditivo Ponderado Linear)
        const double E_norm = 100.0 * e0;
        const double P_100 = 100.0 * (dm / (dm + params.k_produtiva));
        const double S_100 = 50.0 * soc_base;
        n.ecologica = E_norm;
        n.produtiva = P_100;
        n.social = S_100;
        n.resiliencia = params.we * E_norm + params.wp * P_100 + params.ws * S_100;
    } else if (params.modelo == MODELO_EXP_003) {
        // EPS-EXP-003 (Interativo com Acoplamento Cruzado)
        const double E = 0.5 + e0;
        const double P = 50.0 * (dm / (dm + params.k_produtiva));
        const double S = 25.0 * soc_base;
        n.ecologica = E;
        n.produtiva = P;
        n.social = S;
        const double sinergia = params.lambda_interativo * (P * S / 50.0);
        n.resiliencia = E * (P + S) + sinergia;
    } else {
        // EPS-EXP-004 / EPS-DIR-MUN-001 (Autonomo Municipal)
        const double E = 0.5 + e0;
        const double P = 50.0 * (dm / (dm + params.k_produtiva));
        const double S = 25.0 * soc_base;
        n.ecologica = E;
        n.produtiva = P;
        n.social = S;
        n.resiliencia = estado(E, P, S);
    }

    n.status = "experimental";
    return n;
}

std::vector<Nota> confrontar_modelos(const RawMunicipio& m, const ParametrosExperimento& params) {
    std::vector<Nota> resultados;
    const std::vector<std::string> modelos = {MODELO_REF_001, MODELO_EXP_002, MODELO_EXP_003, MODELO_EXP_004};
    for (const auto& mod : modelos) {
        ParametrosExperimento p = params;
        p.modelo = mod;
        resultados.push_back(pontuar(m, p));
    }
    return resultados;
}
}
