/*
 * @file PassThrough.sv
 * @brief Hardware block with ready/valid interface and 3-state FSM
 *
 * Implements a READY -> BUSY -> VALID FSM:
 *   READY : accepts input (in_ready=1), waits for in_valid
 *   BUSY  : one-cycle processing stage
 *   VALID : presents output (out_valid=1), waits for out_ready
 */

module PassThrough (
    input  logic        clk,
    input  logic        reset,

    // Input interface (connected to previous stage)
    input  logic [31:0] in_data,
    input  logic        in_valid,
    output logic        in_ready,

    // Output interface (connected to next stage)
    output logic [31:0] out_data,
    output logic        out_valid,
    input  logic        out_ready
);

    // ========================================
    // FSM state definition
    // ========================================
    typedef enum logic [1:0] {
        READY = 2'b00,
        BUSY  = 2'b01,
        VALID = 2'b10
    } state_t;

    state_t current_state, next_state;

    // Data register
    logic [31:0] data_reg;

    // -------------------------------------------------------------------------
    // FSM : state register
    // -------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (reset)
            current_state <= READY;
        else
            current_state <= next_state;
    end

    // -------------------------------------------------------------------------
    // FSM : next-state logic
    // -------------------------------------------------------------------------
    always_comb begin
        next_state = current_state;
        case (current_state)
            READY:   if (in_valid)   next_state = BUSY;
            BUSY:                    next_state = VALID;
            VALID:   if (out_ready)  next_state = READY;
            default:                 next_state = READY;
        endcase
    end

    // -------------------------------------------------------------------------
    // FSM : output logic
    // -------------------------------------------------------------------------
    always_comb begin
        in_ready  = 1'b0;
        out_valid = 1'b0;
        case (current_state)
            READY:   in_ready  = 1'b1;
            VALID:   out_valid = 1'b1;
            default: begin
                in_ready  = 1'b0;
                out_valid = 1'b0;
            end
        endcase
    end

    // -------------------------------------------------------------------------
    // Data register : capture input on READY -> BUSY transition
    // -------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (reset)
            data_reg <= 32'h0;
        else if (current_state == READY && in_valid)
            data_reg <= in_data;
    end

    assign out_data = data_reg;

endmodule