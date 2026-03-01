// six_hump_camel.c
// Simple C code computing the six-hump camel function.
// Reads x0 and x1 from input.txt and writes f to f_output.txt.

#include <stdio.h>
#include <stdlib.h>
#include <math.h>

int main(void)
{
    double x0, x1, f;

    FILE *fin = fopen("input.txt", "r");
    fscanf(fin, "x0 = %lf", &x0);
    fscanf(fin, "x1 = %lf", &x1);
    fclose(fin);

    // Six-hump camel function
    f = (4 - 2.1 * x0 * x0 + pow(x0, 4) / 3.0) * x0 * x0
        + x0 * x1
        + (-4 + 4 * x1 * x1) * x1 * x1;

    FILE *fout = fopen("output.txt", "w");
    fprintf(fout, "%.10f\n", f);
    fclose(fout);

    return 0;
}
