#include "resiliencia/model.hpp"
#include <algorithm>
#include <charconv>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
// CSV de intercambio normalizado RFC4180; texto UTF-8; separador virgula.
std::vector<std::vector<std::string>> ler_csv(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) throw std::runtime_error("Nao foi possivel abrir "+path);
    std::vector<std::vector<std::string>> rows;
    std::vector<std::string> row;
    std::string field;
    bool quote = false;
    for (int ic; (ic=in.get()) != EOF;) {
        char c=static_cast<char>(ic);
        if (c=='\"') {
            if (quote && in.peek()=='\"') { in.get(); field+='\"'; }
            else quote=!quote;
        } else if (c==',' && !quote) { row.push_back(field); field.clear(); }
        else if ((c=='\n'||c=='\r') && !quote) {
            if (c=='\r' && in.peek()=='\n') in.get();
            row.push_back(field); field.clear();
            if (!(row.size()==1 && row[0].empty())) rows.push_back(row);
            row.clear();
        } else field+=c;
    }
    if (quote) throw std::runtime_error("CSV com aspas nao fechadas");
    if (!row.empty()||!field.empty()) { row.push_back(field); rows.push_back(row); }
    if (rows.empty()) throw std::runtime_error("CSV vazio");
    // Remover BOM UTF-8 do cabecalho, se existir.
    if (rows[0][0].rfind("\xEF\xBB\xBF",0)==0) rows[0][0].erase(0,3);
    return rows;
}
std::string quote_csv(std::string x) {
    if (x.find_first_of(",\"\n\r")==std::string::npos) return x;
    std::string o="\"";
    for (char c:x) {if (c=='\"') o+='\"'; o+=c;}
    return o+'\"';
}
std::optional<double> number(std::string s) {
    if (s.empty()||s=="NA"||s==".."||s=="..."||s=="X"||s=="-") return {};
    double v{};
    auto [end,err]=std::from_chars(s.data(),s.data()+s.size(),v);
    if (err!=std::errc{}||end!=s.data()+s.size()||!std::isfinite(v)) return {};
    return v;
}
std::string number_csv(const std::optional<double>& x) {
    if (!x) return "";
    std::ostringstream o; o<<std::fixed<<std::setprecision(6)<<*x; return o.str();
}
std::string escape_json(const std::string& s) {
    std::string out;
    for (char c:s) {if(c=='\"'||c=='\\') out+='\\'; if(c=='\n') out+="\\n"; else if(c=='\r') out+="\\r"; else out+=c;}
    return out;
}
std::vector<resiliencia::RawMunicipio> converter(const std::vector<std::vector<std::string>>& rows, bool prototype) {
    const std::vector<std::string> campos={"codigo_ibge","municipio","ano_referencia","area_estabelecimentos_ha","pastagem_natural_ha","mata_natural_ha","valor_producao_reais","estabelecimentos_total","estabelecimentos_orientacao_tecnica","estabelecimentos_associados"};
    std::map<std::string,size_t> idx;
    for (size_t j=0;j<rows[0].size();j++) idx[rows[0][j]]=j;
    for(const auto& c:campos) if(!idx.contains(c)) throw std::runtime_error("Falta coluna: "+c);
    std::set<std::string> ids; std::vector<resiliencia::RawMunicipio> out;
    for(size_t i=1;i<rows.size();++i) {
        const auto& x=rows[i];
        auto get=[&](const std::string& c)->std::string{size_t k=idx.at(c);return k<x.size()?x[k]:"";};
        auto id=get("codigo_ibge");
        if (!prototype && (id.size()!=7||id.substr(0,2)!="43"||!std::all_of(id.begin(),id.end(),[](unsigned char c){return c>='0'&&c<='9';})))
            throw std::runtime_error("Codigo IBGE invalido na linha "+std::to_string(i+1));
        if (id.empty()||!ids.insert(id).second) throw std::runtime_error("ID vazio/duplicado: "+id);
        auto ano=get("ano_referencia");
        if(ano!="2017") throw std::runtime_error("Este modelo requer referencia 2017; linha "+std::to_string(i+1));
        out.push_back({id,get("municipio"),ano,
            number(get("area_estabelecimentos_ha")),number(get("pastagem_natural_ha")),number(get("mata_natural_ha")),
            number(get("valor_producao_reais")),number(get("estabelecimentos_total")),
            number(get("estabelecimentos_orientacao_tecnica")),number(get("estabelecimentos_associados"))});
    }
    if(!prototype && out.size()!=497) throw std::runtime_error("Publicacao bloqueada: esperados 497 municipios, recebidos "+std::to_string(out.size()));
    if(out.empty()) throw std::runtime_error("Nenhum municipio fornecido");
    return out;
}
void executar(const std::string& entrada,const std::string& saida, bool prototipo) {
    auto dados=converter(ler_csv(entrada),prototipo);
    auto cal=resiliencia::calibrar(dados);
    std::ofstream out(saida);
    if(!out) throw std::runtime_error("Nao posso criar arquivo "+saida);
    out<<"codigo_ibge,municipio,ano_referencia,ecologica_indice,ecologica_multiplicador,produtiva,social,resiliencia,status\n";
    int validos=0, faltantes=0, inconsistentes=0;
    for(const auto& d:dados) {
        auto n=resiliencia::pontuar(d,cal);
        if(n.status=="experimental") ++validos; else if(n.status=="inconsistencia") ++inconsistentes; else ++faltantes;
        out<<quote_csv(n.codigo)<<","<<quote_csv(n.nome)<<","<<n.referencia<<","<<number_csv(n.ecol_indice)<<","<<number_csv(n.ecologica)<<","<<number_csv(n.produtiva)<<","<<number_csv(n.social)<<","<<number_csv(n.resiliencia)<<","<<n.status<<"\n";
    }
    if(!out) throw std::runtime_error("Falha ao escrever CSV");
    const auto meta=std::filesystem::path(saida).replace_extension(".manifest.json");
    std::ofstream j(meta);
    if(!j) throw std::runtime_error("Nao posso criar manifesto");
    j<<"{\n  \"model_id\": \""<<resiliencia::MODEL_VERSION<<"\",\n"
     <<"  \"status\": \""<<(prototipo?"PROTOTIPO_NAO_HOMOLOGADO":"CALCULADO_PENDENTE_AUDITORIA_FONTE")<<"\",\n"
     <<"  \"referencia\": \"2017\",\n  \"universo\": \"estabelecimentos agropecuarios, nao todo o municipio\",\n"
     <<"  \"entrada\": \""<<escape_json(entrada)<<"\",\n"
     <<"  \"municipios\": "<<dados.size()<<",\n  \"validos\": "<<validos<<",\n  \"incompletos\": "<<faltantes<<",\n  \"inconsistentes\": "<<inconsistentes<<",\n"
     <<"  \"calibracao\": {\"variavel\": \"log1p(valor_producao_reais / area_estabelecimentos_ha)\", \"q10\": "<<std::setprecision(15)<<cal.log_valor_ha_q10<<", \"q90\": "<<cal.log_valor_ha_q90<<", \"n\": "<<cal.observacoes<<"},\n"
     <<"  \"equacao\": \"R = E * (P + S)\",\n"
     <<"  \"aviso\": \"Sem vinculo automatico com IBGE. Conferir tabela, categorias e unidades no SIDRA; validar insumos antes do uso cientifico. Comparacoes temporais exigem calibracao fixa e compatibilidade.\"\n}\n";
    std::cout<<"Modelo "<<resiliencia::MODEL_VERSION<<" | "<<dados.size()<<" municipios | validos="<<validos<<" | faltantes="<<faltantes<<" | inconsistentes="<<inconsistentes<<"\n"
             <<"Resultados: "<<saida<<"\nManifesto: "<<meta.string()<<"\n";
}
}
int main(int argc, char** argv) {
    try {
        if(argc<2) {std::cerr<<"Uso: resiliencia-rs compute <entrada.csv> <saida.csv> [--prototype]\n";return 2;}
        std::string op=argv[1];
        if(op=="compute" && (argc==4 || argc==5)) {
            bool proto=(argc==5 && std::string(argv[4])=="--prototype");
            if (argc==5 && !proto) throw std::runtime_error("Argumento nao reconhecido");
            executar(argv[2],argv[3],proto); return 0;
        }
        std::cerr<<"Comando invalido. Uso: resiliencia-rs compute <entrada.csv> <saida.csv> [--prototype]\n";
        return 2;
    } catch(const std::exception& e) {std::cerr<<"ERRO: "<<e.what()<<"\n"; return 1;}
}
