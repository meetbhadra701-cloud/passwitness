module reduction_control(
    input signed [7:0] a,
    input signed [7:0] b,
    output signed [15:0] y
);
    // passwitness-reduce-begin: correct_unused_a
    wire signed [15:0] unused_a = a * 16'sd11;
    wire signed [15:0] unused_b = unused_a + 16'sd7;
    // passwitness-reduce-end: correct_unused_a
    // passwitness-reduce-begin: correct_unused_b
    wire signed [15:0] unused_c = b * 16'sd13;
    wire signed [15:0] unused_d = unused_c - 16'sd9;
    // passwitness-reduce-end: correct_unused_b
    assign y = a * 16'sd3 + b * -16'sd2;
endmodule

module reduction_fault(
    input signed [7:0] a,
    input signed [7:0] b,
    output signed [15:0] y
);
    // passwitness-reduce-begin: fault_unused_a
    wire signed [15:0] unused_a = a * 16'sd11;
    wire signed [15:0] unused_b = unused_a + 16'sd7;
    // passwitness-reduce-end: fault_unused_a
    // passwitness-reduce-begin: fault_unused_b
    wire signed [15:0] unused_c = b * 16'sd13;
    wire signed [15:0] unused_d = unused_c - 16'sd9;
    // passwitness-reduce-end: fault_unused_b
    assign y = a * 16'sd3 + b * -16'sd2 + 16'sd1;
endmodule
