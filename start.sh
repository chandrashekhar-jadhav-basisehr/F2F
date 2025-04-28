#!/bin/bash

# Optional: sleep to let system services stabilize
sleep 10

cd /home/ubuntu/projects/singleapi
source venv/bin/activate

# CUDA base path
export CUDA_HOME=/usr/local/cuda-12.1

# cuDNN include and library paths
export CUDNN_INCLUDE_DIR=/usr/local/cuda-12.1/targets/x86_64-linux/include
export CUDNN_LIB_DIR=/lib/x86_64-linux-gnu

# Update PATH and LD_LIBRARY_PATH
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$CUDNN_LIB_DIR:$LD_LIBRARY_PATH


echo "Activated venv"

# Wait for NVIDIA driver and GPU to be accessible
until nvidia-smi &> /dev/null
do
    echo "Waiting for NVIDIA driver..."
    sleep 5
done
echo "NVIDIA ready"

# Wait until CUDA inside venv is functional (torch can see GPU)
until python3 -c "import torch; assert torch.cuda.is_available()" &> /dev/null
do
    echo "Waiting for torch.cuda in venv..."
    sleep 5
done
echo "Torch sees GPU"

# Now finally launch the server
nohup python3 app.py >> clienttesting1.log 2>&1 &
