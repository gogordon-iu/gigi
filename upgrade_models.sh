#!/bin/bash
# ==============================================================================
# Gigi Robot - Automated Model Upgrade Script
# ==============================================================================
# This script automates the download of the Qwen-2.5-3B-Instruct NPU-accelerated
# model and updates the local LLM server script on the Orange Pi 5.
# ==============================================================================

set -e

RESOURCES_DIR="/home/orangepi/Code/gigi/Resources"
MODEL_PATH="${RESOURCES_DIR}/qwen2.5_3b.rkllm"
MODEL_URL="https://huggingface.co/c01zaut/Qwen2.5-3B-Instruct-rk3588-1.1.1/resolve/main/qwen2.5_3b_instruct_w8a8.rkllm"
LLM_SERVER_SH="/home/orangepi/Code/gigi/llm_server.sh"

echo "=== [Gigi Model Upgrade] Creating Resources directory if missing ==="
mkdir -p "${RESOURCES_DIR}"

echo "=== [Gigi Model Upgrade] Downloading Qwen-2.5-3B-Instruct (.rkllm) ==="
echo "From: ${MODEL_URL}"
echo "To:   ${MODEL_PATH}"
echo "This might take several minutes (approx. 3.2 GB)..."

if [ -f "${MODEL_PATH}" ]; then
    echo "[!] Model file already exists at ${MODEL_PATH}. Skipping download."
else
    # Download with progress bar, resume capability, and redirect to target file
    wget -c -O "${MODEL_PATH}" "${MODEL_URL}"
    echo "[+] Model downloaded successfully!"
fi

echo "=== [Gigi Model Upgrade] Updating llm_server.sh ==="
if [ -f "${LLM_SERVER_SH}" ]; then
    echo "[+] Backing up existing llm_server.sh to llm_server.sh.bak"
    cp "${LLM_SERVER_SH}" "${LLM_SERVER_SH}.bak"
fi

echo "[+] Writing updated llm_server.sh pointing to 3B model..."
cat << 'EOF' > "${LLM_SERVER_SH}"
#!/bin/bash
cd /home/orangepi/Code/gigi/Resources/rknn-llm/examples/rkllm_server_demo/rkllm_server/
python3 flask_server.py --rkllm_model_path /home/orangepi/Code/gigi/Resources/qwen2.5_3b.rkllm --target_platform rk3588
EOF

chmod +x "${LLM_SERVER_SH}"

echo "=== [Gigi Model Upgrade] Complete! ==="
echo "To launch the upgraded LLM server, run:"
echo "  sudo ./llm_server.sh"
echo "=============================================================================="
