
// ----------------------------------------------------------------------------------
// universal_simulation_top.sv
// 
// Wrapper de simulation permettant de choisir dynamiquement entre :
// 1. Simulation directe du cœur (Bypass UART) pour tests unitaires rapides
// 2. Simulation système complet via UART (PC <-> UART <-> FPGA)
//
// ----------------------------------------------------------------------------------

module universal_simulation_top (
    input  logic       clk,
    input  logic       reset,
    
    // ==========================================
    // CONFIGURATION
    // ==========================================
    input  logic       bypass_uart, // 1 = Mode Direct, 0 = Mode UART Simulation

    // ==========================================
    // INTERFACE 1 : MODE DIRECT (Bypass)
    // ==========================================
    // Connecté directement au top_level quand bypass_uart = 1
    input  logic [7:0] direct_in_data,
    input  logic       direct_in_valid,
    output logic [7:0] direct_out_data,
    output logic       direct_out_valid,

    // ==========================================
    // INTERFACE 2 : MODE UART (Simulation PC)
    // ==========================================
    // Simule l'envoi/réception série depuis un PC quand bypass_uart = 0
    input  logic [7:0] pc_tx_byte,   // Octet que le PC envoie
    input  logic       pc_tx_en,     // Valid envoi PC
    output logic [7:0] pc_rx_byte,   // Octet reçu par le PC
    output logic       pc_rx_valid,  // Valid réception PC
    output logic       pc_uart_busy  // Si l'UART PC est occupé
);

    // -------------------------------------------------------------------------
    // 1. Instanciation des UARTs "Côté PC" (Simulateur / Banc de test)
    // -------------------------------------------------------------------------
    logic sim_cable_pc_to_fpga;
    logic sim_cable_fpga_to_pc;
    logic host_fifo_full;
    logic host_fifo_afull;
    logic host_fifo_empty;

    // Le PC envoie (TX) -> vers FPGA (RX)
    UART_fifoed_send #( 
        .baudrate(115200),
        .clock_frequency(100000000) 
    ) inst_host_tx (
        .clk_100MHz(clk),
        .reset(reset),
        .dat_en(pc_tx_en),
        .dat(pc_tx_byte),
        .TX(sim_cable_pc_to_fpga),
        .fifo_full(host_fifo_full),
        .fifo_afull(host_fifo_afull),
        .fifo_empty(host_fifo_empty)
    );
    
    // Le PC reçoit (RX) <- depuis FPGA (TX)
    UART_recv inst_host_rx (
        .clk(clk),
        .reset(reset),
        .rx(sim_cable_fpga_to_pc),
        .dat(pc_rx_byte),
        .dat_en(pc_rx_valid)
    );

    assign pc_uart_busy = host_fifo_full;

    // -------------------------------------------------------------------------
    // 2. Instanciation des UARTs "Côté FPGA" (Hardware réel simulé)
    // -------------------------------------------------------------------------
    logic [7:0] uart_to_core_data;
    logic       uart_to_core_valid;
    
    logic [7:0] core_to_uart_data;
    logic       core_to_uart_valid;
    
    logic       fpga_fifo_full;
    logic       fpga_fifo_afull;
    logic       fpga_fifo_empty;

    // FPGA RX (Reçoit du Câble PC)
    UART_recv inst_fpga_rx (
        .clk(clk),
        .reset(reset),
        .rx(sim_cable_pc_to_fpga),
        .dat(uart_to_core_data),
        .dat_en(uart_to_core_valid)
    );

    // FPGA TX (Envoie vers le Câble PC)
    UART_fifoed_send #( 
        .baudrate(115200),
        .clock_frequency(100000000)
    ) inst_fpga_tx (
        .clk_100MHz(clk),
        .reset(reset),
        .dat_en(core_to_uart_valid), 
        .dat(core_to_uart_data),
        .TX(sim_cable_fpga_to_pc),
        .fifo_full(fpga_fifo_full),
        .fifo_afull(fpga_fifo_afull),
        .fifo_empty(fpga_fifo_empty)
    );

    // -------------------------------------------------------------------------
    // 3. Logique de MUX / BYPASS
    // -------------------------------------------------------------------------
    logic [7:0] final_core_input_data;
    logic       final_core_input_valid;

    // Multiplexage des entrées vers le User Core
    assign final_core_input_data  = (bypass_uart) ? direct_in_data  : uart_to_core_data;
    assign final_core_input_valid = (bypass_uart) ? direct_in_valid : uart_to_core_valid;

    // Monitoring permanent de la sortie du User Core sur le port direct
    assign direct_out_data  = core_to_uart_data;
    assign direct_out_valid = core_to_uart_valid;

    // -------------------------------------------------------------------------
    // 4. Instanciation du TOP LEVEL Utilisateur
    // -------------------------------------------------------------------------
    // Note : On suppose une interface standard data/valid. 
    // Si votre Top_Level utilise Ready/Valid, il faudra gérer le 'ready' ici
    // (ex: lier ready vers uart_fifo_full).
    
    Top_Level inst_user_core (
        .clk(clk),
        .reset(reset),
        
        // Input
        .in_data(final_core_input_data),
        .in_valid(final_core_input_valid),
        // .in_ready(), // Ignoré pour cet exemple simple (le UART RX ne check pas le ready)

        // Output
        .out_data(core_to_uart_data),
        .out_valid(core_to_uart_valid)
        // .out_ready(!fpga_fifo_full) // On pourrait utiliser le full flag pour backpressure
    );

endmodule
