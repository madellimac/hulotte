module universal_simulation_top (
    input  logic       clk,
    input  logic       reset,
    input  logic       use_uart_select,  // Runtime selection: 1 = UART, 0 = Direct
    
    // ==========================================
    // INTERFACE 1 : MODE DIRECT (Bypass)
    // ==========================================
    input  logic [7:0] direct_in_data,
    input  logic       direct_in_valid,
    output logic [7:0] direct_out_data,
    output logic       direct_out_valid,

    // ==========================================
    // INTERFACE 2 : MODE UART (Simulation PC)
    // ==========================================
    input  logic [7:0] pc_tx_byte,
    input  logic       pc_tx_en,
    output logic [7:0] pc_rx_byte,
    output logic       pc_rx_valid,
    output logic       pc_uart_busy
);

    // Signaux d'interface vers le User Core
    logic [7:0] final_core_input_data;
    logic       final_core_input_valid;
    
    // Signaux sortant du User Core
    logic [7:0] core_to_uart_data;
    logic       core_to_uart_valid;

    // Signal de backpressure vers le User Core
    logic       core_out_ready;

    // Monitoring permanent de la sortie du User Core sur le port direct
    assign direct_out_data  = core_to_uart_data;
    assign direct_out_valid = core_to_uart_valid;

    // Signaux internes UART
    logic sim_cable_pc_to_fpga;
    logic sim_cable_fpga_to_pc;
    
    logic host_fifo_full;
    logic host_fifo_afull;
    logic host_fifo_empty;
    
    logic [7:0] uart_to_core_data;
    logic       uart_to_core_valid;
    
    logic       fpga_fifo_full;
    logic       fpga_fifo_afull;
    logic       fpga_fifo_empty;

    // -------------------------------------------------------------------------
    // ALWAYS SYNTHESIZE BOTH PATHS, USE RUNTIME MUX FOR SELECTION
    // -------------------------------------------------------------------------
    
    // UART PATH (always synthesized)
    UART_fifoed_send #( 
        .baudrate(10000000), 
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
    
    UART_recv  #( 
        .baudrate(10000000), 
        .clock_frequency(100000000) 
    ) inst_host_rx (
        .clk(clk),
        .reset(reset),
        .rx(sim_cable_fpga_to_pc),
        .dat(pc_rx_byte),
        .dat_en(pc_rx_valid)
    );

    assign pc_uart_busy = host_fifo_full;

    UART_recv  #( 
        .baudrate(10000000), 
        .clock_frequency(100000000) 
    ) inst_fpga_rx (
        .clk(clk),
        .reset(reset),
        .rx(sim_cable_pc_to_fpga),
        .dat(uart_to_core_data),
        .dat_en(uart_to_core_valid)
    );

    UART_fifoed_send #( 
        .baudrate(10000000), 
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

    // RUNTIME MUX: Choose input path based on use_uart_select signal
    assign final_core_input_data  = use_uart_select ? uart_to_core_data : direct_in_data;
    assign final_core_input_valid = use_uart_select ? uart_to_core_valid : direct_in_valid;
    
    // RUNTIME MUX: Backpressure control based on selected path
    assign core_out_ready = use_uart_select ? !fpga_fifo_full : 1'b1;

    // -------------------------------------------------------------------------
    // Instanciation du TOP LEVEL Utilisateur
    // -------------------------------------------------------------------------
    
    // Adaptation de largeur pour Top_Level (32 bits) vs UART (8 bits)
    logic [31:0] core_in_data_32;
    logic [31:0] core_out_data_32;
    
    assign core_in_data_32 = {24'b0, final_core_input_data}; // Zero-pad input
    assign core_to_uart_data = core_out_data_32[7:0];       // Truncate output to 8 bits

    Top_Level inst_user_core (
        .clk(clk),
        .reset(reset),
        
        // Input
        .in_data(core_in_data_32),
        .in_valid(final_core_input_valid),
        .in_ready(), // Sortie non-utilisée par le wrapper (Backpressure vers RX non géré ici)

        // Output
        .out_data(core_out_data_32),
        .out_valid(core_to_uart_valid),
        .out_ready(core_out_ready) 
    );

endmodule