module top(
    input [3:0] a,
    output [3:0] y
);
    assign y = a + 4'd1;
endmodule

module wrong_candidate(
    input [3:0] b,
    output [3:0] z
);
    assign z = b;
endmodule
