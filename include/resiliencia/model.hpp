#pragma once
#include <optional>
#include <string>
#include <vector>

namespace resiliencia {
// Versao segundo Diretriz Metodologica METIS-DIR-MUN-001:
// O municipio e a unidade individual de analise; calculo 100% independente de outros municipios.
inline constexpr const char* MODEL_VERSION = "EPS-DIR-MUN-001/0.2.0";

struct RawMunicipio {
    std::string codigo, nome, referencia;
    std::optional<double> area_ha, pastagem_natural_ha, mata_natural_ha;
    std::optional<double> valor_producao_reais;
    std::optional<double> estabelecimentos, com_orientacao, associados;
};

struct ParametrosExperimento {
    // Escala de saturacao da densidade monetaria dm = VP / A (R$/ha).
    // Quando dm = k, P = 25.0 (exatamente a metade da escala [0, 50]).
    double k_produtiva = 1500.0;
};

struct Nota {
    std::string codigo, nome, referencia, status;
    std::optional<double> densidade_monetaria_ha; // dm = VP / A (R$/ha)
    std::optional<double> ecol_indice;            // e = (pastagem + mata) / A
    std::optional<double> ecologica;              // E = 0.5 + clamp(e, 0, 1)
    std::optional<double> produtiva;              // P = 50 * dm / (dm + k)
    std::optional<double> social;                 // S = 25 * (orient + coop) / estab
    std::optional<double> resiliencia;            // R = E * (P + S)
    double k_utilizado = 0.0;
};

std::optional<double> densidade_monetaria(const RawMunicipio& m);
Nota pontuar(const RawMunicipio& m, const ParametrosExperimento& params);
double estado(double E, double P, double S);
}
