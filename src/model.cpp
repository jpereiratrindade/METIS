#include "resiliencia/model.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <vector>
namespace resiliencia {
namespace {
bool ok(const std::optional<double>& x) { return x && std::isfinite(*x) && *x >= 0; }
double clip(double x, double lo, double hi) { return std::clamp(x, lo, hi); }
double quantile(const std::vector<double>& x, double q) {
    if (x.empty()) throw std::invalid_argument("quantile sem observacoes");
    double p = (x.size()-1)*q; auto a = static_cast<size_t>(std::floor(p)); auto b = static_cast<size_t>(std::ceil(p));
    return x[a] + (x[b]-x[a])*(p-a);
}
}
double estado(double E, double P, double S) {
    if (!(std::isfinite(E)&&std::isfinite(P)&&std::isfinite(S)&&E>0&&P>=0&&S>=0))
        throw std::invalid_argument("Estado invalido: E>0, P>=0, S>=0");
    return E*(P+S);
}
std::optional<double> valor_por_ha_log(const RawMunicipio& m) {
    if (!(ok(m.area_ha)&&*m.area_ha>0&&ok(m.valor_producao_reais))) return {};
    return std::log1p(*m.valor_producao_reais / *m.area_ha);
}
Calibracao calibrar(const std::vector<RawMunicipio>& municipios) {
    std::vector<double> x;
    for (const auto& m: municipios) if (auto v = valor_por_ha_log(m)) x.push_back(*v);
    std::sort(x.begin(), x.end());
    if (x.empty()) return {};
    return {quantile(x,0.10), quantile(x,0.90), static_cast<int>(x.size())};
}
Nota pontuar(const RawMunicipio& m, const Calibracao& cal) {
    Nota n{m.codigo,m.nome,m.referencia,"dados_incompletos",{},{},{},{},{}};
    if (!(ok(m.area_ha) && *m.area_ha>0 && ok(m.pastagem_natural_ha) && ok(m.mata_natural_ha)
        && ok(m.valor_producao_reais) && ok(m.estabelecimentos) && *m.estabelecimentos>0
        && ok(m.com_orientacao) && ok(m.associados))) return n;
    if (*m.pastagem_natural_ha + *m.mata_natural_ha > *m.area_ha + 1e-7
        || *m.com_orientacao > *m.estabelecimentos || *m.associados > *m.estabelecimentos) {
        n.status="inconsistencia"; return n;
    }
    const double e0 = clip((*m.pastagem_natural_ha + *m.mata_natural_ha) / *m.area_ha, 0, 1);
    const double E = 0.5 + e0;
    const double log_val_ha = std::log1p(*m.valor_producao_reais / *m.area_ha);
    const double p01 = (cal.log_valor_ha_q90 > cal.log_valor_ha_q10)
        ? clip((log_val_ha-cal.log_valor_ha_q10)/(cal.log_valor_ha_q90-cal.log_valor_ha_q10),0,1)
        : 0.5; // referencia nao discriminante: registrar manifest
    const double P = 50 * p01;
    const double S = 25 * ((*m.com_orientacao + *m.associados) / *m.estabelecimentos);
    n.ecol_indice=e0; n.ecologica=E; n.produtiva=P; n.social=S; n.resiliencia=estado(E,P,S);
    n.status="experimental";
    return n;
}
}
