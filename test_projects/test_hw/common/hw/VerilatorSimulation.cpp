#include <stdlib.h>
#include <iostream>
#include <verilated.h>          
// On inclut le header généré par Verilator pour le nouveau module top
#include "Vuniversal_simulation_top.h"       
#include "VerilatorSimulation.hpp"

using namespace spu;
using namespace spu::module;

    VerilatorSimulation::VerilatorSimulation(int frame_size) : Stateful(), frame_size(frame_size) {

        // Instanciation du nouveau wrapper
        dut = new Vuniversal_simulation_top;  

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

        // Producer FSM states (2 states: BUSY, VALID)
        enum producer_state_t { PRODUCER_BUSY = 0, PRODUCER_VALID = 1 };
        producer_state_t producer_current = PRODUCER_BUSY;
        producer_state_t producer_next = PRODUCER_BUSY;
        
        // Consumer FSM states (2 states: READY, BUSY)
        enum consumer_state_t { CONSUMER_READY = 0, CONSUMER_BUSY = 1 };
        consumer_state_t consumer_current = CONSUMER_READY;
        consumer_state_t consumer_next = CONSUMER_READY;

        int init_time = sim_time;

        while(output_data_count < frame_size) {
            
            if(is_reset_time()){
                dut->reset = 1;
                dut->i_valid = 0;
                dut->o_ready = 1;
                producer_current = PRODUCER_BUSY;
                producer_next = PRODUCER_BUSY;
                consumer_current = CONSUMER_READY;
                consumer_next = CONSUMER_READY;
            }
            else if(is_rising_edge()){
                dut->reset = 0;
                producer_current = producer_next;
                consumer_current = consumer_next;
            }
            else if(is_falling_edge()){
                dut->reset = 0;
                
                // ===== PRODUCER FSM =====
                // State: BUSY (waiting) -> VALID (sending) -> BUSY
                switch(producer_current) {
                    case PRODUCER_BUSY:
                        // Waiting to send data
                        // Check if DUT is ready and we have data to send
                        if(input_data_count < frame_size && dut->i_ready) {
                            // DUT is ready, prepare to send
                            dut->i_valid = 1;
                            dut->i_data = input[input_data_count];
                            producer_next = PRODUCER_VALID;
                        } else {
                            // Keep waiting
                            dut->i_valid = 0;
                            dut->i_data = 0;
                            producer_next = PRODUCER_BUSY;
                        }
                        break;
                        
                    case PRODUCER_VALID:
                        // Data was sent on previous cycle
                        // Increment counter and return to waiting
                        input_data_count++;
                        dut->i_valid = 0;
                        dut->i_data = 0;
                        producer_next = PRODUCER_BUSY;
                        break;
                }
                
                // ===== CONSUMER FSM =====
                // State: READY (consuming) -> BUSY (received) -> READY
                switch(consumer_current) {
                    case CONSUMER_READY:
                        // Ready to accept output data
                        dut->o_ready = 1;
                        
                        // Check if valid data is available
                        if(dut->o_valid) {
                            // DUT has valid data, capture it
                            if(output_data_count < frame_size) {
                                output[output_data_count++] = dut->o_data;
                            }
                            consumer_next = CONSUMER_BUSY;
                        } else {
                            // No valid data yet, stay ready
                            consumer_next = CONSUMER_READY;
                        }
                        break;
                        
                    case CONSUMER_BUSY:
                        // Just received data on previous cycle
                        // Return to ready state for next transaction
                        dut->o_ready = 0;
                        consumer_next = CONSUMER_READY;
                        break;
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
