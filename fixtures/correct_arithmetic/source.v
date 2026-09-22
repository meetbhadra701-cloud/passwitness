module correct_arithmetic(
    input signed [3:0] a,
    input signed [3:0] b,
    output signed [7:0] y
);
    assign y = a * 8'sd3 + b * -8'sd2;
endmodule
