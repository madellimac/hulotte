// ----------------------------------------------------------------------------------
// 
//  UART_recv_
//  Version 1.2b
//  Written by Yannick Bornat (2014/01/27)
//  Updated by Yannick Bornat (2014/05/12) : output is now synchronous
//  Updated by Yannick Bornat (2014/06/10) :
//     V1.1 : totally rewritten 
//        reception is now more reliable
//        for 3Mbps @50MHz, it is safer to use 1.5 or 2 stop bits.
//  Updated by Yannick Bornat (2014/08/04) :
//     V1.2 : Added slow values for instrumentation compatibility
//  Updated by Yannick Bornat (2015/08/21) :
//     V1.2b : Simplified to fit ENSEIRB-MATMECA lab sessions requirements
// 
//  Receives a char on the UART line
//  dat_en is set for one clock period when a char is received 
//  dat must be read at the same time
//  Designed for 100MHz clock, reset is active high
//  transfer rate is 115 200kbps
// 
// ----------------------------------------------------------------------------------

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

    typedef enum logic [2:0] {
        IDLE,             // the normal waiting state (input should always be 1)
        ZERO_AS_INPUT,    // we received a '1' in input but it may be noise
        WAIT_NEXT_BIT,    // we just received an input that remained unchanged for 1/4 of the bit period, we wait for 3/4 to finish timeslot
        BIT_SAMPLE,       // we wait for a bit to last at least 1/4 of the period without changing
        BIT_RECEIVED,     // a bit was received during 1/4 of period, so it is valid
        WAIT_STOP_BIT,    // the last bit was a stop, we wait for it to finish (1/2 of period)
        LAST_BIT_IS_ZERO  // well last bit was not a stop, we wait for a 1 that lasts a full period...
    } t_fsm;

    t_fsm state = IDLE;
    int   nbbits = 0;
    int   cnt = 0;
    logic rxi = 1'b1;
    logic ref_bit;
    logic [7:0] shift;

    localparam int bit_period       = clock_frequency / baudrate;
    localparam int quarter          = bit_period / 4;
    localparam int half             = bit_period / 2;
    localparam int three_quarters   = (bit_period * 3) / 4;
    localparam int full             = bit_period - 1;

    // we fisrt need to sample the input signal
    always_ff @(posedge clk) begin
        rxi <= rx;
    end

    // the FSM of the module...
    always_ff @(posedge clk) begin
        if (reset) begin
            state <= IDLE;
        end else begin
            case (state)
                IDLE: begin
                    if (rxi == 1'b0) state <= ZERO_AS_INPUT;
                end
                
                ZERO_AS_INPUT: begin
                    if (rxi == 1'b1) state <= IDLE;
                    else if (cnt == 0) state <= WAIT_NEXT_BIT;
                end
                
                WAIT_NEXT_BIT: begin
                    if (cnt == 0) state <= BIT_SAMPLE;
                end
                
                BIT_SAMPLE: begin
                    if (cnt == 0) state <= BIT_RECEIVED;
                end
                
                BIT_RECEIVED: begin
                    if (nbbits < 8)       state <= WAIT_NEXT_BIT;
                    else if (ref_bit == 1'b1) state <= WAIT_STOP_BIT;
                    else                  state <= LAST_BIT_IS_ZERO;
                end
                
                WAIT_STOP_BIT: begin
                    if (rxi == 1'b0)      state <= LAST_BIT_IS_ZERO;
                    else if (cnt == 0)    state <= IDLE;
                end
                
                LAST_BIT_IS_ZERO: begin
                    if (cnt == 0) state <= IDLE;
                end
                
                default: state <= IDLE;
            endcase
        end
    end

    // here we manage the counter 
    always_ff @(posedge clk) begin
        if (reset) begin
            cnt <= quarter;
        end else begin
            case (state)
                IDLE: cnt <= quarter;
                
                ZERO_AS_INPUT: begin
                    if (cnt == 0) cnt <= three_quarters; // transition, we prepare the next waiting time
                    else          cnt <= cnt - 1;
                end
                
                WAIT_NEXT_BIT: begin
                    if (cnt == 0) cnt <= quarter;        // transition, we prepare the next waiting time
                    else          cnt <= cnt - 1;
                end
                
                BIT_SAMPLE: begin
                    if (ref_bit != rxi) cnt <= quarter;  // if bit change, we restart the counter
                    else                cnt <= cnt - 1;
                end
                
                BIT_RECEIVED: begin
                    if (nbbits < 8)       cnt <= three_quarters;
                    else if (ref_bit == 1'b0) cnt <= full;
                    else                  cnt <= half;
                end
                
                WAIT_STOP_BIT: cnt <= cnt - 1;
                
                LAST_BIT_IS_ZERO: begin
                    if (rxi == 1'b0) cnt <= full;
                    else             cnt <= cnt - 1;
                end
                
                default: cnt <= cnt - 1;
            endcase
        end
    end

    // we now manage the reference bit that should remain constant for 1/4 period during bit_sample
    // we affect ref_bit in both wait_next_bit (so that we arrive in bit_sample with initialized value)
    // and in bit_sample because if different, we consider each previous value as a mistake, and if equal
    // it has no consequence...
    always_ff @(posedge clk) begin
        if (state == WAIT_NEXT_BIT || state == BIT_SAMPLE) begin
            ref_bit <= rxi;
        end
    end

    // output (shift) register
    always_ff @(posedge clk) begin
        if (state == BIT_SAMPLE && cnt == 0 && nbbits < 8) begin
            shift <= {ref_bit, shift[7:1]};
        end
    end

    // nbbits management
    always_ff @(posedge clk) begin
        if (state == IDLE) begin
            nbbits <= 0;
        end else if (state == BIT_RECEIVED) begin
            nbbits <= nbbits + 1;
        end
    end

    // outputs
    always_ff @(posedge clk) begin
        if (reset) begin
            dat_en <= 1'b0;
        end else if (state == WAIT_STOP_BIT && cnt == 0) begin
            dat_en <= 1'b1;
            dat    <= shift;
        end else begin
            dat_en <= 1'b0;
        end
    end

endmodule
