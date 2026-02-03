#include <iostream>
#include <streampu.hpp>

using namespace spu;
using namespace spu::module;

int main()
{
    const  int FRAME_SIZE = 20;
    const int MAX_VAL = 63;
    
    module::Initializer   <int> initializer(FRAME_SIZE);
    module::Incrementer   <int> incr(FRAME_SIZE);
    module::Finalizer     <int> finalizer_sw(FRAME_SIZE);
    
    std::cout << "Starting ex1_spu_only example..." << std::endl;   
    initializer ["initialize::out" ] = incr           ["increment::in"];
    incr        ["increment::out"   ] = finalizer_sw        ["finalize::in"];
    
    std::vector<runtime::Task*> first = {&initializer("initialize")};
    
    runtime::Sequence seq(first);

    std::ofstream file("graph.dot");
    seq.export_dot(file);

    for (auto lt : seq.get_tasks_per_types())
        for (auto t : lt)
        {
            t->set_stats(true);
            t->set_debug(true);
        }

    for(auto i = 0; i < 3; i++)
    {
        seq.exec_seq();
    }

    tools::Stats::show(seq.get_tasks_per_types(), true, false);
}