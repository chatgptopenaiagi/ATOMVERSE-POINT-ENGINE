import json
import math
from pathlib import Path
import time
import torch
import numpy as np

root=Path(__file__).resolve().parents[1]
report={'measured':True,'torch':torch.__version__,'cuda':torch.version.cuda,'cudnn':torch.backends.cudnn.version(),'gpu':torch.cuda.get_device_name(0)}
def bench(fn,n,sync=False):
    for _ in range(3): fn()
    if sync: torch.cuda.synchronize()
    t=time.perf_counter()
    for _ in range(n): fn()
    if sync: torch.cuda.synchronize()
    return (time.perf_counter()-t)/n*1e6
report['one_point_math_us']=bench(lambda:(2*math.cos(.5),2*math.sin(.5),.4*.5),100000)
t=torch.tensor([.5],device='cuda',dtype=torch.float64)
report['one_point_cuda_with_readback_us']=bench(lambda:torch.stack((2*torch.cos(t),2*torch.sin(t),.4*t)).cpu().tolist(),500,True)
for device in ('cpu','cuda'):
    t=torch.linspace(0,100,100000,device=device,dtype=torch.float64)
    report[device+'_100000_points_resident_us']=bench(lambda:torch.stack((2*torch.cos(t),2*torch.sin(t),.4*t)),50,device=='cuda')
    report[device+'_tensor_device']=str(t.device)
conv=torch.nn.Conv2d(3,8,3).cuda(); x=torch.ones((1,3,32,32),device='cuda')
report['cudnn_convolution_shape']=list(conv(x).shape); torch.cuda.synchronize()
a=np.ones(4*1024*1024,dtype=np.float64); b=np.empty_like(a)
us=bench(lambda:np.copyto(b,a),24)
report['memory_copy_effective_GB_s']=a.nbytes*2/(us*1e-6)/1e9
report['memory_copy_method']='32 MiB numpy copy, 24 repetitions; read+write bytes, cache/OS effects included; not peak DRAM bandwidth'
report['selected']='CPU scalar math for one point; GPU OpenGL rasterization. CUDA remains optional for measured future batched workloads.'
(root/'EVIDENCE/CPU-GPU-PERFORMANCE.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
