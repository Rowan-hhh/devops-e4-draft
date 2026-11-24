#include <stdio.h>

int print_value(int value) {
    return printf("%d\n", value) < 0 ? 1 : 0;
}
