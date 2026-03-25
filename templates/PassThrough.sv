/*
 * @file PassThrough.sv
 * @brief Frame-Based Processing Template
 *
 * Supports configurable FRAME_SIZE and separates INPUT/OUTPUT logic.
 * Default behavior: Simple Pipeline (1-cycle latency, streaming)
 */

module PassThrough #(
    parameter int FRAME_SIZE = 16
)(
    input  logic        clk,
    input  logic        reset,

    // Input Stream
    input  logic [31:0] in_data,
    input  logic        in_valid,
    output logic        in_ready,

    // Output Stream
    output logic [31:0] out_data,
    output logic        out_valid,
    input  logic        out_ready
);

    localparam int CNT_W = $clog2(FRAME_SIZE + 1);
    typedef logic [CNT_W-1:0] cnt_t;
    localparam cnt_t FRAME_LAST = cnt_t'(FRAME_SIZE - 1);

    // =========================================================================
    // 1. INPUT STAGE: Receive Frame
    // =========================================================================
    cnt_t                            cnt_in;
    logic                            input_fire;

    // Handshake logic:
    // - Accept a new word when output register is empty OR downstream is ready.
    // - This guarantees no data loss under backpressure and allows 1 word/cycle throughput
    //   when downstream keeps out_ready asserted.
    assign in_ready   = !reset && (!out_valid || out_ready);
    assign input_fire = in_valid && in_ready;

    // Input Counter
    always_ff @(posedge clk) begin
        if (reset) begin
            cnt_in <= '0;
        end else if (input_fire) begin
            if (cnt_in == FRAME_LAST)
                cnt_in <= '0;
            else
                cnt_in <= cnt_in + 1;
        end
    end

    // =========================================================================
    // 2. PROCESSING / STORAGE STAGE
    // =========================================================================
    // Single-stage register slice with backpressure support
    logic [31:0] pipe_data;
    logic        pipe_valid;

    always_ff @(posedge clk) begin
        if (reset) begin
            pipe_valid <= 1'b0;
            pipe_data  <= '0;
        end else if (in_ready) begin
            // Shift/accept phase: if downstream consumes (or buffer was empty),
            // publish new input validity and data in the same cycle.
            pipe_valid <= in_valid;
            if (in_valid)
                pipe_data <= in_data;
        end
        // else: hold data/valid while stalled (out_valid && !out_ready)
    end

    // =========================================================================
    // 3. OUTPUT STAGE: Transmit Frame
    // =========================================================================
    cnt_t                            cnt_out;
    logic                            output_fire;

    assign out_data    = pipe_data;
    assign out_valid   = pipe_valid;
    assign output_fire = out_valid && out_ready;

    // Output Counter
    always_ff @(posedge clk) begin
        if (reset) begin
            cnt_out <= '0;
        end else if (output_fire) begin
            if (cnt_out == FRAME_LAST)
                cnt_out <= '0;
            else
                cnt_out <= cnt_out + 1;
        end
    end

    // =========================================================================
    // OPTIONAL: End-of-Frame Signal (useful for debug/control)
    // =========================================================================
    logic frame_done;
    assign frame_done = (cnt_out == FRAME_LAST) && output_fire;

endmodule
