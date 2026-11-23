#include "scale.h"
#include "clamp.h"

int scale(int value) {
    int scaled = value * SCALE_NUM / SCALE_DEN;
    return scaled > QUOTA_MAX ? QUOTA_MAX : scaled;
}
