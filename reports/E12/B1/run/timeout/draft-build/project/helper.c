#include <stdio.h>
#include "output_format.h"

int print_value(int value) {
    return printf(OUTPUT_FORMAT, value) < 0 ? 1 : 0;
}
