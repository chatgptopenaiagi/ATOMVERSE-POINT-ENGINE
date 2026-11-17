#include <cmath>
#include <iostream>
int main() {
    double x=2*std::cos(0.5), y=2*std::sin(0.5);
    if (std::abs(x*x+y*y-4)>1e-12) return 1;
    std::cout << "C++ x64 trajectory arithmetic PASS\n";
    return 0;
}
