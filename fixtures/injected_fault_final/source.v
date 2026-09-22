module final_correct(
    input [7:0] a,
    input [7:0] b,
    output [7:0] y
);
    assign y = a + b;
endmodule

module final_wrong(
    input [7:0] a,
    input [7:0] b,
    output [7:0] y
);
    assign y = a ^ b;
endmodule
