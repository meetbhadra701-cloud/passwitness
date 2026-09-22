module fma_impl #(
    parameter W = 4
) (
    input signed [W-1:0] a, b,
    output signed [W+15:0] y
);
    wire signed [W+15:0] sa = {{16{a[W-1]}}, a};
    wire signed [W+15:0] sb = {{16{b[W-1]}}, b};
    wire signed [W+15:0] p0 = sa * 24'sd3;
    wire signed [W+15:0] p1 = sb * -24'sd2;
    assign y = p0 + p1;
endmodule
