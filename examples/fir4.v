module fir4 #(
    parameter W = 4
) (
    input signed [W-1:0] x0, x1, x2, x3,
    output signed [W+15:0] y
);
    assign y = x0 * 24'sd3 + x1 * -24'sd2 + x2 * 24'sd5 + x3;
endmodule
