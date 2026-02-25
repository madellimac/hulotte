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

        enum t_state { wait, shift_in, shift_out, over };
        t_state c_state, n_state = wait;
        int i =0;
        int init_time = sim_time;
        int val;

        // while (sim_time < 10000) {
        while(output_data_count < frame_size) {
            
            // --- CONFIGURATION DU MODE ---
            // bypass_uart = 1 -> Simulation directe (comme avant)
            // bypass_uart = 0 -> Simulation via UART
            dut->bypass_uart = 1; 

            if(is_reset_time()){
                dut->reset = 1;
                // Signal "in_valid" de l'interface directe (anciennement dut->in_valid)
                dut->direct_in_valid = 0;
                // Pour éviter des indéterminés sur l'UART simulé si bypass=0
                dut->pc_tx_en = 0; 
            }
            else if(is_rising_edge()){
                dut->reset = 0;       
                c_state = n_state;     
            }
            else if(is_falling_edge()){
                dut->reset = 0;
                
                // --- OUTPUT HANDLING (Mode Direct) ---
                // Le top level actuel n'a pas forcément de "ready" en retour vers nous dans le wrapper,
                // on suppose qu'on est toujours prêts à lire la sortie directe.
                
                // (Si vous utilisiez out_ready dans Top_Level, il faut le mapper dans universal_simulation_top)
                // dut->direct_out_ready = 1; 

                if (dut->direct_out_valid) {
                    if (output_data_count < frame_size) {
                        output[output_data_count++] = dut->direct_out_data;
                    }
                }

                // --- INPUT HANDLING (Mode Direct) ---
                
                // 1. On vérifie si l'injection précédente a été prise
                // On suppose ici que le wrapper/core est toujours prêt (in_ready pas exposé dans wrapper universel de base)
                // Si votre Top_Level a un in_ready, il faut l'exposer dans universal_simulation_top.sv
                // Comme le wrapper n'avait pas in_ready dans l'exemple, on assume success.
                bool handshake_success = dut->direct_in_valid == 1; 

                if (handshake_success) {
                    input_data_count++;
                }

                // 2. Drive new data
                if (input_data_count < frame_size) {
                    dut->direct_in_valid = 1;         
                    dut->direct_in_data = input[input_data_count];
                } else {
                    dut->direct_in_valid = 0;
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
