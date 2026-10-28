#pragma once
#include <optional>
#include <string>
#include <vector>

namespace resiliencia {
inline constexpr const char* MODEL_VERSION = "EPS-REF-001/0.1.0";
struct RawMunicipio {
    std::string codigo, nome, referencia;
    std::optional<double> area_ha, pastagem_natural_ha, mata_natural_ha;
    std::optional<double> valor_producao_reais;
    std::optional<double> estabelecimentos, com_orientacao, associados;
};
struct Calibracao {
    double log_valor_ha_q10 = 0, log_valor_ha_q90 = 0;
    int observacoes = 0;
};
struct Nota {
    std::string codigo, nome, referencia, status;
    std::optional<double> ecol_indice, ecologica, produtiva, social, resiliencia;
};
std::optional<double> valor_por_ha_log(const RawMunicipio& m);
Calibracao calibrar(const std::vector<RawMunicipio>& municipios);
Nota pontuar(const RawMunicipio& m, const Calibracao& cal);
double estado(double E, double P, double S);
}
