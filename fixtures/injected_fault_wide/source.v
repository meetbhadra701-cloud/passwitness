module wide_correct(
    input signed [5:0] a,
    input signed [5:0] b,
    output signed [11:0] y
);
    assign y = a * 6'sd7 + b * 6'sd3;
endmodule

module wide_wrong(
    input signed [5:0] a,
    input signed [5:0] b,
    output signed [11:0] y
);
    assign y = a * 6'sd7 + b * 6'sd4;
endmodule
