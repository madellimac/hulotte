module universal_simulation_top (
    input  logic       clk,
    input  logic       reset,
    
    // ==========================================
    // Interface Ready/Valid d'entrée
    // ==========================================
    input  logic [7:0] i_data,
    input  logic       i_valid,
    output logic       i_ready,
    
    // ==========================================
    // Interface Ready/Valid de sortie
    // ==========================================
    output logic [7:0] o_data,
    output logic       o_valid,
    input  logic       o_ready
);

    // Définition des états de la FSM
    typedef enum logic [1:0] {
        READY = 2'b00,
        BUSY  = 2'b01,
        VALID = 2'b10
    } state_t;
    
    state_t current_state, next_state;
    
    // Registre de données (8 bits)
    logic [7:0] data_reg;
    
    // -------------------------------------------------------------------------
    // FSM : Registre d'état
    // -------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (reset) begin
            current_state <= READY;
        end else begin
            current_state <= next_state;
        end
    end
    
    // -------------------------------------------------------------------------
    // FSM : Logique de transition d'états
    // -------------------------------------------------------------------------
    always_comb begin
        // Valeurs par défaut
        next_state = current_state;
        
        case (current_state)
            READY: begin
                // Attend une donnée valide en entrée
                if (i_valid) begin
                    next_state = BUSY;
                end
            end
            
            BUSY: begin
                // Traitement (pour l'instant instantané)
                next_state = VALID;
            end
            
            VALID: begin
                // Attend que le consommateur soit prêt
                if (o_ready) begin
                    next_state = READY;
                end
            end
            
            default: begin
                next_state = READY;
            end
        endcase
    end
    
    // -------------------------------------------------------------------------
    // FSM : Logique de sortie
    // -------------------------------------------------------------------------
    always_comb begin
        // Valeurs par défaut
        i_ready = 1'b0;
        o_valid = 1'b0;
        
        case (current_state)
            READY: begin
                i_ready = 1'b1;  // Prêt à recevoir des données
                o_valid = 1'b0;
            end
            
            BUSY: begin
                i_ready = 1'b0;
                o_valid = 1'b0;
            end
            
            VALID: begin
                i_ready = 1'b0;
                o_valid = 1'b1;  // Données valides en sortie
            end
            
            default: begin
                i_ready = 1'b0;
                o_valid = 1'b0;
            end
        endcase
    end
    
    // -------------------------------------------------------------------------
    // Registre de données : mémorisation de l'entrée
    // -------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (reset) begin
            data_reg <= 8'h00;
        end else if (current_state == READY && i_valid) begin
            // Capture la donnée d'entrée lors de la transaction
            data_reg <= i_data;
        end
    end
    
    // -------------------------------------------------------------------------
    // Sortie : données mémorisées
    // -------------------------------------------------------------------------
    assign o_data = data_reg;

endmodule