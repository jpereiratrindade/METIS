#include "resiliencia/model.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace resiliencia;
static void check(bool b, const std::string& msg) { if(!b) throw std::runtime_error("Teste falhou: "+msg); }
int main() {
    try {
        check(std::abs(estado(0.7,35,30)-45.5)<1e-9,"amortecimento E<1");
        check(std::abs(estado(1,35,30)-65)<1e-9,"neutralidade E=1");
        check(std::abs(estado(1.3,35,30)-84.5)<1e-9,"amplificacao E>1");
        bool failure=false; try{(void)estado(0,1,2);}catch(...){failure=true;}
        check(failure,"E=0 invalido");
        RawMunicipio m{"TEST-001","Sintetico", "2017", 100,30,20,100000,100,40,60};
        Calibracao c{0,10,1};
        auto n=pontuar(m,c);
        check(n.status=="experimental","nota calculada");
        check(std::abs(*n.ecologica-1.0)<1e-12,"E de referencia 1");
        check(std::abs(*n.social-25.0)<1e-12,"S proporcoes");
        m.com_orientacao=101;
        check(pontuar(m,c).status=="inconsistencia","numerador excede denominador");
        m.com_orientacao={};
        check(pontuar(m,c).status=="dados_incompletos","ausencia nao e zero");
        std::cout<<"9 verificacoes cientificas basicas aprovadas\n";return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
