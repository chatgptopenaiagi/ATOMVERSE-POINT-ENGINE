#include <cuda_runtime.h>
#include <cstdio>
__global__ void square(float* x) { x[threadIdx.x]*=x[threadIdx.x]; }
int main() {
    float input[2]={2,3}; float* device=nullptr;
    if(cudaMalloc(&device,sizeof(input))!=cudaSuccess) return 1;
    if(cudaMemcpy(device,input,sizeof(input),cudaMemcpyHostToDevice)!=cudaSuccess) return 2;
    square<<<1,2>>>(device);
    if(cudaDeviceSynchronize()!=cudaSuccess) return 3;
    if(cudaMemcpy(input,device,sizeof(input),cudaMemcpyDeviceToHost)!=cudaSuccess) return 4;
    cudaFree(device);
    if(input[0]!=4 || input[1]!=9) return 5;
    std::puts("CUDA compiled kernel on real GPU PASS"); return 0;
}
