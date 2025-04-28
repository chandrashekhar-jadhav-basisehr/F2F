#!/bin/bash

sudo apt update -y
 
sudo apt install -y git-lfs python3-dev python3-venv python3-pip poppler-utils build-essential libpq-dev

# Exit on error
set -e

# Function to check command status
check_status() {
    if [ $? -ne 0 ]; then
        echo "Error: $1 failed"
        exit 1
    fi
}

# Clone SingleAPI repository
git clone https://git.digiquanta.com/monad/singleapi.git
check_status "Cloning SingleAPI"
cd singleapi/

# Display remote branches and checkout integration
git branch -r
git checkout main2
check_status "Checkout main2 branch"

# Setup Python virtual environment
python3 -m venv venv
. venv/bin/activate
check_status "Virtual environment setup"

# Install Python requirements
pip install -r requirements.txt
check_status "Installing Python requirements"

# Setup Git LFS
git lfs install
git lfs --version
check_status "Git LFS setup"

# Clone model repositories
repos=(
    "https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct"
    "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct"
    "https://huggingface.co/Digiquanta/Facesheets-Classification"
    "https://huggingface.co/Raunak554/Documents-Classification"
    "https://huggingface.co/Raunak554/yolo_finetune_for_sign_date_detection"
)

for repo in "${repos[@]}"; do
    echo "Cloning $repo"
    git clone "$repo"
    check_status "Cloning $repo"
done

echo "Setup completed successfully"