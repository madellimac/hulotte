#include <stdlib.h>
#include <iostream>
#include <verilated.h>          
#include "VTop_Level.h"       
#include "VerilatorSimulation.hpp"

using namespace spu;
using namespace spu::module;

    VerilatorSimulation::VerilatorSimulation(int frame_size) : Stateful(), frame_size(frame_size) {

        dut = new VTop_Level;  // Remplacer "your_module" par le nom de votre module Verilog

        Verilated::traceEverOn(true);
        m_trace = new VerilatedVcdC;
        dut->trace(m_trace, 5);
        m_trace->open("waveform.vcd");
        
        this->set_name("VerilatorSimulation");
        this->set_short_name("VerilatorSimulation");

        auto &t = create_task("simulate");

        auto input    = create_socket_in<int>(t, "input", frame_size);
        auto output   = create_socket_out<int>(t, "output", frame_size);

        this->create_codelet(t, [input, output](Module &m, runtime::Task &t, const size_t frame_id) -> int {
        static_cast<VerilatorSimulation&>(m).simulate(  static_cast<int*>(t[input].get_dataptr()),
                                                        static_cast<int*>(t[output].get_dataptr()),
                                                        frame_id);
        return 0;
    });

    }

    VerilatorSimulation::~VerilatorSimulation() {
        m_trace->close();
        delete m_trace;
        delete dut;
        // exit(EXIT_SUCCESS);
    }    

    void VerilatorSimulation::simulate(const int* input, int *output, const int frame_id) {
        
        int input_data_count = 0;
        int output_data_count = 0;

        enum t_state { wait, shift_in, shift_out, over };
        t_state c_state, n_state = wait;
        int i =0;
        int init_time = sim_time;
        int val;

        // while (sim_time < 10000) {
        while(output_data_count < frame_size) {
            
            if(is_reset_time()){
                dut->reset = 1;
                dut->out_ready = 0;
            }
            else if(is_rising_edge()){
                dut->reset = 0;       
                c_state = n_state;     
            }
            else if(is_falling_edge()){
                dut->reset = 0;
                
                // --- OUTPUT HANDLING ---
                dut->out_ready = 1; // Always ready to receive
                
                if (dut->out_valid) {
                    if (output_data_count < frame_size) {
                        output[output_data_count++] = dut->out_data;
                    }
                }

                // --- INPUT HANDLING ---
                
                // 1. Check if handshake occurred at the previous Rising Edge
                // If Valid (we drove) and Ready (DUT drove) were both high, the data was taken.
                if (dut->in_valid && dut->in_ready) {
                    input_data_count++;
                }

                // 2. Drive new data for the next Rising Edge
                if (input_data_count < frame_size) {
                    dut->in_valid = 1;         
                    dut->in_data = input[input_data_count];
                } else {
                    dut->in_valid = 0;
                }
            }
            
            dut->clk ^= 1;
            dut->eval();

            m_trace->dump(sim_time);

            sim_time++;
           
        }
    }

    // Ajoutez d'autres méthodes pour contrôler votre simulation au besoin


    bool VerilatorSimulation::is_reset_time(){
        return (sim_time < 7);
    }

    bool VerilatorSimulation::is_rising_edge(){
        return (sim_time%2 == 0);
    }

    bool VerilatorSimulation::is_falling_edge(){
        return (sim_time%2 != 0);
    }