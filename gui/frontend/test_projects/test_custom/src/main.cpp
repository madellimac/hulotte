
#include <iostream>
#include <vector>
#include <fstream>
#include <streampu.hpp>



#include "custom/MyModule.hpp"


#include "Comparator.hpp"

using namespace spu;
using namespace spu::module;

int main(int argc, char** argv)
{
    std::cout << "Starting Hulotte project..." << std::endl;


    // 1. Modules creation

    const int n_elmts = 16;
    module::Source_random<int> source(n_elmts);
    Comparator                  comparator(n_elmts);
    
    
    module::MyModule         my_module(n_elmts);
    
    

    // 2. Sockets binding
    
    // in_ref: source directly to comparator (reference -- unchanged data)
    source["generate::out_data"] = comparator["check::in_ref"];

    
    // Custom module mode: source -> custom module -> comparator
    source["generate::out_data"] = my_module["process::in"];
    my_module["process::out"]    = comparator["check::in_got"];
    
    


    // 3. Sequence creation
    std::vector<runtime::Task*> first_tasks;
    first_tasks.push_back(&source("generate"));

    runtime::Sequence sequence(first_tasks);

    // Configuration
    for (auto& type : sequence.get_tasks_per_types())
        for (auto& t : type)
        {
            t->set_stats(true);
            t->set_debug(true);
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
    std::cout << "\nEnd of execution." << std::endl;
    tools::Stats::show(sequence.get_tasks_per_types(), true, false);

    // 6. Non-regression check
    if (comparator.has_errors())
        std::cerr << "[FAIL] " << comparator.get_n_errors() << " error(s) detected over "
                  << comparator.get_frame_count() << " frame(s)." << std::endl;
    else
        std::cout << "[PASS] 0 errors over " << comparator.get_frame_count() << " frame(s)." << std::endl;

    return comparator.has_errors() ? 1 : 0;
}
