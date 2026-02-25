#ifndef VERILATORSIMULATION_H
#define VERILATORSIMULATION_H

#include <verilated.h>          // Pour Verilator
#include <verilated_vcd_c.h>    // Pour la trace VCD
//#include "Module/Module.hpp"
#include "streampu.hpp"

// On change la déclaration anticipée pour le nouveau Top unique
class Vuniversal_simulation_top;

namespace spu
{
namespace module
{

class VerilatorSimulation  : public Stateful {

private:
    
    // Pointeur vers le modèle Verilator généré du wrapper universel
    Vuniversal_simulation_top* dut; 

    VerilatedVcdC* m_trace;
    vluint64_t sim_time = 0;
    vluint64_t MAX_SIM_TIME = 300;

    int frame_size;

    bool is_reset_time();
    bool is_rising_edge();
    bool is_falling_edge();


public:

    VerilatorSimulation(int frame_size);
    virtual ~VerilatorSimulation();

protected:

    virtual void simulate(const int* input, int *output, const int frame_id);

};
}
}

#endif // VERILATORSIMULATION_H
