/*
 * @file PassThrough.sv
 * @brief Default pass-through hardware block with ready/valid interface
 * 
 * This is created by default when you generate a new project with --hw.
 * You can replace this with your own logic while keeping the interface.
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
    // Pass-through implementation
    // ========================================
    
    // in_ready is combinatorial - always follow out_ready
    assign in_ready = !reset && out_ready;
    
    always_ff @(posedge clk) begin
        if (reset) begin
            out_valid <= 1'b0;
            out_data  <= 32'b0;
        end else if (in_valid && in_ready) begin
            // Pass data through on valid && ready transfer
            out_data  <= in_data;
            out_valid <= 1'b1;
        end else if (out_ready) begin
            // Clear output when downstream consumes data
            out_valid <= 1'b0;
        end
    end

endmodule
