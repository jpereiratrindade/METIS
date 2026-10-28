#pragma once
#include <optional>
#include <string>
#include <vector>

namespace resiliencia {

inline constexpr const char* MODELO_REF_001 = "EPS-REF-001";
inline constexpr const char* MODELO_EXP_002 = "EPS-EXP-002";
inline constexpr const char* MODELO_EXP_003 = "EPS-EXP-003";
inline constexpr const char* MODELO_EXP_004 = "EPS-EXP-004";
inline constexpr const char* DEFAULT_MODEL_VERSION = "EPS-REF-001/0.1.0";

struct RawMunicipio {
    std::string codigo, nome, referencia;
    std::optional<double> area_ha, pastagem_natural_ha, mata_natural_ha;
    std::optional<double> valor_producao_reais;
    std::optional<double> estabelecimentos, com_orientacao, associados;
};

struct ParametrosExperimento {
    std::string modelo = "EPS-REF-001";

    // Parametros para EPS-REF-001 (calibracao historica estadual via percentis)
    double q10 = 7.27298934926942;
    double q90 = 8.93207610159435;

    // Parametro de escala k (R$/ha) para funcoes de saturacao (usado em EXP-002, EXP-003, EXP-004)
    double k_produtiva = 1500.0;

    // Pesos da hipotese aditiva linear (EPS-EXP-002)
    double we = 0.33, wp = 0.33, ws = 0.34;

    // Intensidade da sinergia socio-produtiva interativa (EPS-EXP-003)
    double lambda_interativo = 0.5;
};

struct Nota {
    std::string codigo, nome, referencia, status;
    std::string modelo;
    std::optional<double> densidade_monetaria_ha; // dm = VP / A (R$/ha)
    std::optional<double> ecol_indice;            // e = (pastagem + mata) / A
    std::optional<double> ecologica;              // E
    std::optional<double> produtiva;              // P
    std::optional<double> social;                 // S
    std::optional<double> resiliencia;            // R
    double k_utilizado = 0.0;
};

std::optional<double> densidade_monetaria(const RawMunicipio& m);
Nota pontuar(const RawMunicipio& m, const ParametrosExperimento& params);
std::vector<Nota> confrontar_modelos(const RawMunicipio& m, const ParametrosExperimento& params);
double estado(double E, double P, double S);
}

