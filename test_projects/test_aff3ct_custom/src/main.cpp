
#include <iostream>
#include <vector>
#include <fstream>
#include <streampu.hpp>

#include <aff3ct.hpp>



#include "custom/MyModule.hpp"


using namespace spu;
using namespace spu::module;

int main(int argc, char** argv)
{
    std::cout << "Starting Hulotte project..." << std::endl;


    // 1. Modules creation
    
    // RS(255, 239) => t=8, m=8. Bits 2040 -> 1912.
    // NOTE: This uses aff3ct B_32 (32-bit integer) template instantiation.
    const int N_rs = 255;  // Symbols
    const int K_rs = 239;  // Symbols
    const int m = 8;       // Bits per symbol
    const int t = (N_rs - K_rs) / 2; // Correction power
    const int N = N_rs * m; // Total bits
    const int K = K_rs * m; // Info bits

    module::Source_random<> source(K);
    module::Finalizer    <> finalizer(K);
    
    // Create RS Polynomial Generator (needed for RS construction)
    aff3ct::tools::RS_polynomial_generator poly(N_rs, t);
    
    // Create Encoder and Decoder
    aff3ct::module::Encoder_RS<>     encoder(K_rs, N_rs, poly);
    aff3ct::module::Decoder_RS_std<> decoder(K_rs, N_rs, poly);    

    
    module::MyModule         my_module(K);
    
    

    // 2. Sockets binding
    using namespace aff3ct::module;
    using namespace aff3ct::tools;
    
    // Chain construction
    source   [src::tsk::generate][(int)src::sck::generate::out_data] = 
    
    my_module ["process::in"];
    my_module ["process::out"] = 
    
    
    encoder  [enc::tsk::encode][(int)enc::sck::encode::U_K];

    encoder  [enc::tsk::encode][(int)enc::sck::encode::X_N]        = decoder  [dec::tsk::decode_hiho][(int)dec::sck::decode_hiho::Y_N];
    decoder  [dec::tsk::decode_hiho][(int)dec::sck::decode_hiho::V_K] = finalizer["finalize::in"];



    // 3. Sequence creation
    std::vector<runtime::Task*> first_tasks;

    first_tasks.push_back(&source("generate"));


    runtime::Sequence sequence(first_tasks);

    // Configuration
    for (auto& type : sequence.get_tasks_per_types())
        for (auto& t : type)
        {
            t->set_stats(true);
            t->set_debug(false);
        }

    // 4. Execution
    std::cout << "Processing..." << std::endl;
    
    // Export dot file for visualization
    std::ofstream file("graph.dot");
    sequence.export_dot(file);

    // Run the sequence
    for (auto i = 0; i < 3; i++)
        sequence.exec_seq(); // Run 1 frame at a time

    // 5. Stats
    std::cout << "\\nEnd of execution." << std::endl;
    tools::Stats::show(sequence.get_tasks_per_types(), true, false);

    return 0;
}
