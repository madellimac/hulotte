module UART_recv #(
    parameter int baudrate = 115200,
    parameter int clock_frequency = 100000000
)(
    input  logic       clk,
    input  logic       reset,
    input  logic       rx,
    output logic [7:0] dat,
    output logic       dat_en
);
    // Period calculation
    localparam int CLKS_PER_BIT = clock_frequency / baudrate;

    typedef enum logic [2:0] {
        IDLE,
        START_BIT,
        DATA_BITS,
        STOP_BIT,
        CLEANUP
    } t_state;

    t_state state = IDLE;
    
    // Counter for clock ticks
    int clk_cnt = 0;
    
    // Index for data bits (0-7)
    int bit_idx = 0;
    
    // Temporary storage
    logic [7:0] rx_byte = 0;

    // Double-flop synchronizer for RX input (CDC safety)
    logic rx_sync_1 = 1;
    logic rx_sync   = 1;

    always_ff @(posedge clk) begin
        if (reset) begin
            rx_sync_1 <= 1;
            rx_sync   <= 1;
        end else begin
            rx_sync_1 <= rx;
            rx_sync   <= rx_sync_1;
        end
    end

    always_ff @(posedge clk) begin
        if (reset) begin
            state   <= IDLE;
            clk_cnt <= 0;
            bit_idx <= 0;
            dat_en  <= 0;
            dat     <= 0;
            rx_byte <= 0;
        end else begin
            case (state)
                IDLE: begin
                    dat_en  <= 0;
                    clk_cnt <= 0;
                    bit_idx <= 0;
                    
                    if (rx_sync == 1'b0) begin 
                        // Start bit detected (falling edge)
                        state <= START_BIT;
                    end
                end

                START_BIT: begin
                    // Wait middle of start bit
                    if (clk_cnt == (CLKS_PER_BIT-1)/2) begin
                        if (rx_sync == 1'b0) begin
                            clk_cnt <= 0;
                            state   <= DATA_BITS;
                        end else begin
                            state   <= IDLE;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 1;
                    end
                end

                DATA_BITS: begin
                    if (clk_cnt < CLKS_PER_BIT-1) begin
                        clk_cnt <= clk_cnt + 1;
                    end else begin
                        clk_cnt <= 0;
                        rx_byte[bit_idx] <= rx_sync;
                        
                        if (bit_idx < 7) begin
                            bit_idx <= bit_idx + 1;
                        end else begin
                            bit_idx <= 0;
                            state   <= STOP_BIT;
                        end
                    end
                end

                STOP_BIT: begin
                    if (clk_cnt < CLKS_PER_BIT-1) begin
                        clk_cnt <= clk_cnt + 1;
                    end else begin
                        dat_en  <= 1'b1; // Output valid
                        dat     <= rx_byte;
                        clk_cnt <= 0;
                        state   <= CLEANUP;
                    end
                end

                CLEANUP: begin
                    dat_en <= 1'b0;
                    state  <= IDLE;
                end
                
                default: 
                    state <= IDLE;
            endcase
        end
    end

endmodule
