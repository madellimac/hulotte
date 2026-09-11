
// ----------------------------------------------------------------------------------
// 
//  UART_fifoed_send_V1
//  Version 1.1
//  
//  V1.1 : Translated to SystemVerilog
//        - build from UART_send v1.1, named to fit the same version number
// 
//  Sends chars on the UART line, has a built-in fifo to accept char inputs while
//  sending an older char
//  during character send, busy output bit is set to '1' and the module ignores inputs.
//  works at 100MHz with 115.200kbps transfer rate
// 
// ----------------------------------------------------------------------------------

module UART_fifoed_send #(
    parameter int fifo_size             = 4096,
    parameter int fifo_almost           = 4090,
    parameter bit drop_oldest_when_full = 0,    // boolean False -> 0
    parameter bit asynch_fifo_full      = 1,    // boolean True -> 1
    parameter int baudrate              = 921600,   // [bps]
    parameter int clock_frequency       = 100000000 // [Hz]
) (
    input  logic       clk_100MHz,
    input  logic       reset,
    input  logic       dat_en,
    input  logic [7:0] dat,
    output logic       TX,
    output logic       fifo_empty,
    output logic       fifo_afull,
    output logic       fifo_full
);

    logic [7:0] FIFO [0:fifo_size - 1];

    int   cnt;                            // counter to divide clock events
    logic top;                            // strobe to make state machine progress
    logic [8:0] shift;                    // UART shift register
    int   nbbits;                         // remaining number of bits to transfer
    int   read_index;                     // points to the next element to read from FIFO
    int   write_index;                    // points to the next free room in FIFO array
    int   n_elements;                     // number of elements in FIFO

    logic clk;
    assign clk = clk_100MHz;

    assign top = (cnt == 0);
    assign TX  = shift[0];

    assign fifo_empty = (n_elements == 0);
    assign fifo_afull = (n_elements >= fifo_almost);
    
    // logic equation for fifo_full from VHDL
    // fifo_full  <= '1' when n_elements = fifo_size or 
    //                   (asynch_fifo_full and dat_en = '1' and nbbits < 12 and n_elements = fifo_size - 1)   else '0';
    assign fifo_full = (n_elements == fifo_size) || 
                       (asynch_fifo_full && dat_en && (nbbits < 12) && (n_elements == fifo_size - 1));

    // Baudrate generator process
    always_ff @(posedge clk) begin
        if (reset) begin
            cnt <= 0;
        end else if (nbbits >= 12 || cnt == 0) begin
            cnt <= (clock_frequency / baudrate) - 1;
        end else begin
            cnt <= cnt - 1;
        end
    end

    // UART Shift Register process
    always_ff @(posedge clk) begin
        if (reset) begin
            shift  <= 9'b111111111;
            nbbits <= 12;
        end else if (nbbits >= 12) begin
            // this state waits for data to send
            if (n_elements > 0) begin // data present in fifo
                shift  <= {FIFO[read_index], 1'b0};
                nbbits <= 9;
            end
        end else begin
            // this part actually sends the bits
            if (top) begin
                shift <= {1'b1, shift[8:1]};
                if (nbbits == 0) begin
                    nbbits <= 15;
                end else begin
                    nbbits <= nbbits - 1;
                end
            end
        end
    end

    // Read Index specific process
    always_ff @(posedge clk) begin
        if (reset) begin
            read_index <= 0;
        end else if ((n_elements > 0 && nbbits >= 12) || (dat_en && n_elements == fifo_size && drop_oldest_when_full)) begin
            // conditions to increase read_index :
            //    * sending ready, and fifo not empty
            //    * writing element to FIFO with FIFO full, and prefering to lose oldest element
            if (read_index == fifo_size - 1) begin
                read_index <= 0;
            end else begin
                read_index <= read_index + 1;
            end
        end
    end

    // FIFO n_elements Management process
    always_ff @(posedge clk) begin
        if (reset) begin
            n_elements <= 0;
        end else if (dat_en) begin
            // user wants to write data
            if (n_elements == 0) begin
                // if FIFO is empty, elements must first be written into the array
                // so it will not be read instantly
                n_elements <= 1;
            end else if (nbbits < 12 && n_elements < fifo_size) begin
                // we only increase the number of elements if there is still room
                n_elements <= n_elements + 1;
            end
        end else if (n_elements > 0 && nbbits >= 12) begin
            // no data written, we decrease element number if sending new element
            n_elements <= n_elements - 1;
        end
    end

    // Write Index & memory write process
    always_ff @(posedge clk) begin
        if (reset) begin
            write_index <= 0;
        end else if (dat_en && (n_elements < fifo_size || drop_oldest_when_full)) begin
            // dat_en = '1' means, user wants to write a new element in fifo
            if (write_index == fifo_size - 1) begin
                write_index <= 0;
            end else begin
                write_index <= write_index + 1;
            end
            
            FIFO[write_index] <= dat;
        end
    end

endmodule
