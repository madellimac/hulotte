
#include <iostream>
#include <vector>
#include <fstream>
#include <streampu.hpp>


#include "VerilatorSimulation.hpp"



using namespace spu;
using namespace spu::module;

int main(int argc, char** argv)
{
    std::cout << "Starting Hulotte project..." << std::endl;


    // 1. Modules creation
    const int n_elmts = 16;
    module::Initializer<int> initializer(n_elmts);
    
    module::VerilatorSimulation verilator_sim(n_elmts);
    
    module::Finalizer  <int> finalizer(n_elmts);

    
    
    // 2. Sockets binding
    
    
    
    

    initializer["initialize::out"] = verilator_sim["simulate::input"];
    
    verilator_sim["simulate::output"] = finalizer  ["finalize::in"];
    


    // 3. Sequence creation
    std::vector<runtime::Task*> first_tasks;

    first_tasks.push_back(&initializer("initialize"));


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
