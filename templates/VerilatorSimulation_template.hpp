#ifndef VERILATORSIMULATION_HPP
#define VERILATORSIMULATION_HPP

#include <verilated.h>
#include <verilated_vcd_c.h>
#include <iostream>
#include <streampu.hpp>
#include <memory>

namespace spu
{
namespace module
{

/**
 * Templated Verilator simulation wrapper for generic hardware blocks
 * Works with any hardware block that implements the standard interface:
 * - Inputs: clk, reset, in_data[31:0], in_valid
 * - Outputs: in_ready, out_data[31:0], out_valid
 * - Input: out_ready
 * 
 * Usage:
 *    #include "VModel_increment.h"
 *    auto sim = std::make_unique<VerilatorSimulation<VModel_increment>>(frame_size);
 */
template<typename VModelT>
class VerilatorSimulation : public Stateful {

private:
    VModelT* dut = nullptr; // Pointer to the Verilator generated model
    VerilatedVcdC* m_trace = nullptr;
    VerilatedContext* m_context = nullptr;
    vluint64_t sim_time = 0;
    
    int frame_size;
    std::string trace_name;
    
    bool is_reset_time() { return (sim_time < 7); }
    bool is_rising_edge() { return (sim_time % 2 == 0); }
    bool is_falling_edge() { return (sim_time % 2 != 0); }

public:
    // Public socket instantiation for StreamPU integration
    std::unique_ptr<VModelT> inst_ptr;
    VModelT* inst;

    /**
     * Constructor for Hardware Block Simulation
     * @param frame_size Number of elements per frame
     * @param trace_name Custom name for VCD trace output (optional)
     */
    VerilatorSimulation(int frame_size, const std::string& trace_name = "") 
    : Stateful(), frame_size(frame_size), trace_name(trace_name)
    {
        // 1. Create a dedicated context for this simulation instance
        m_context = new VerilatedContext;
        m_context->traceEverOn(true);
        
        // 2. Instantiate the model using this context
        dut = new VModelT{m_context};
        inst = dut;  // Expose as public interface
        
        // 3. Setup tracing
        Verilated::traceEverOn(true);
        
        std::string final_trace_name = trace_name;
        if (final_trace_name.empty()) {
            final_trace_name = std::string(typeid(VModelT).name()) + ".vcd";
        }
        
        m_trace = new VerilatedVcdC;
        dut->trace(m_trace, 99); // Trace depth
        m_trace->open(final_trace_name.c_str());
        
        // 4. Create module metadata
        const std::string module_name = typeid(VModelT).name();
        this->set_name(module_name);
        this->set_short_name(module_name);
        
        // 5. Create task and sockets
        auto& t = this->create_task("simulate");
        auto p_in  = this->create_socket_in <int32_t>(t, "input",  frame_size);
        auto p_out = this->create_socket_out<int32_t>(t, "output", frame_size);
        
        // 6. Create codelet for execution
        this->create_codelet(t, [p_in, p_out, this](Module &m, runtime::Task &t, const size_t frame_id) -> int
        {
            // Cast to our type
            auto& mod = static_cast<VerilatorSimulation<VModelT>&>(m);
            
            // Get pointers to data
            auto* in_data  = static_cast<int32_t*>(t[p_in].get_dataptr());
            auto* out_data = static_cast<int32_t*>(t[p_out].get_dataptr());
            
            // Process frame
            mod.process_frame(in_data, out_data);
            
            return runtime::status_t::SUCCESS;
        });
    }

    /**
     * Process a single frame of data through the hardware block
     */
    void process_frame(int32_t* in_data, int32_t* out_data) {
        // Simulate the hardware for frame_size cycles
        for (int i = 0; i < frame_size; i++) {
            // Toggle clock each cycle
            dut->clk = (sim_time % 2);
            
            // Set reset during initial cycles
            if (is_reset_time()) {
                dut->reset = 1;
            } else {
                dut->reset = 0;
            }
            
            // On rising edges, set input data and signals
            if (is_rising_edge()) {
                dut->in_data = in_data[i];
                dut->in_valid = 1;
                dut->out_ready = 1;
            }
            
            // Evaluate the model
            dut->eval();
            
            // On falling edges, capture output
            if (is_falling_edge() && !is_reset_time()) {
                if (dut->out_valid) {
                    out_data[i] = dut->out_data;
                }
            }
            
            // Advance simulation time
            sim_time++;
            
            // Update trace
            if (m_trace) {
                m_trace->dump(sim_time);
            }
        }
    }

    /**
     * Destructor - cleanup
     */
    ~VerilatorSimulation() {
        if (m_trace) {
            m_trace->close();
            delete m_trace;
        }
        if (dut) {
            delete dut;
        }
        if (m_context) {
            delete m_context;
        }
    }

    /**
     * Clone support for StreamPU
     */
    virtual VerilatorSimulation* clone() const override {
        auto cloned = new VerilatorSimulation(frame_size, trace_name + "_clone");
        cloned->deep_copy(*this);
        return cloned;
    }
};

}
}

#endif
