#!/bin/bash
# ==============================================================================
# Gigi Robot - Automated Model Upgrade Script
# ==============================================================================
# This script automates the download of the Qwen-2.5-3B-Instruct NPU model,
# the YOLOv11-nano ONNX vision model, and runs verification checks.
# ==============================================================================

set -e

RESOURCES_DIR="/home/orangepi/Code/gigi/Resources"
LLM_MODEL_PATH="${RESOURCES_DIR}/qwen2.5_3b.rkllm"
LLM_MODEL_URL="https://huggingface.co/c01zaut/Qwen2.5-3B-Instruct-rk3588-1.1.1/resolve/main/qwen2.5_3b_instruct_w8a8.rkllm?download=true"
LLM_SERVER_SH="/home/orangepi/Code/gigi/llm_server.sh"

YOLO_MODEL_PATH="${RESOURCES_DIR}/yolo11n.onnx"
YOLO_MODEL_URL="https://huggingface.co/unity/inference-engine-yolo/resolve/main/yolo11n.onnx?download=true"

echo "=== [Gigi Model Upgrade] Creating Resources directory if missing ==="
mkdir -p "${RESOURCES_DIR}"

echo "=== [Gigi Model Upgrade] Downloading Qwen-2.5-3B-Instruct (.rkllm) ==="
echo "From: ${LLM_MODEL_URL}"
echo "To:   ${LLM_MODEL_PATH}"

# Check for invalid/interrupted LLM model downloads (e.g. LFS pointers)
if [ -f "${LLM_MODEL_PATH}" ]; then
    FILE_SIZE=$(wc -c < "${LLM_MODEL_PATH}")
    if [ "$FILE_SIZE" -lt 10000000 ]; then  # Less than 10 MB
        echo "[!] Existing LLM file is too small ($FILE_SIZE bytes), likely a Git LFS pointer. Deleting..."
        rm -f "${LLM_MODEL_PATH}"
    fi
fi

if [ -f "${LLM_MODEL_PATH}" ]; then
    echo "[!] LLM model file already exists and looks valid. Skipping download."
else
    echo "Downloading LLM model (approx. 3.2 GB)..."
    wget -c -O "${LLM_MODEL_PATH}" "${LLM_MODEL_URL}"
    echo "[+] LLM model downloaded successfully!"
fi

echo "=== [Gigi Model Upgrade] Downloading YOLOv11-nano ONNX ==="
echo "From: ${YOLO_MODEL_URL}"
echo "To:   ${YOLO_MODEL_PATH}"

# Check for invalid/interrupted YOLO model downloads (e.g. LFS pointers)
if [ -f "${YOLO_MODEL_PATH}" ]; then
    FILE_SIZE=$(wc -c < "${YOLO_MODEL_PATH}")
    if [ "$FILE_SIZE" -lt 100000 ]; then  # Less than 100 KB
        echo "[!] Existing YOLO file is too small ($FILE_SIZE bytes), likely a Git LFS pointer. Deleting..."
        rm -f "${YOLO_MODEL_PATH}"
    fi
fi

if [ -f "${YOLO_MODEL_PATH}" ]; then
    echo "[!] YOLO model file already exists and looks valid. Skipping download."
else
    echo "Downloading YOLO model (approx. 22 MB)..."
    wget -c -O "${YOLO_MODEL_PATH}" "${YOLO_MODEL_URL}"
    echo "[+] YOLO model downloaded successfully!"
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

echo "=== [Gigi Model Upgrade] Verifying YOLOv11-nano ONNX Model ==="
PYTHON_BIN="python3"
if [ -f ".venv/bin/python3" ]; then
    PYTHON_BIN=".venv/bin/python3"
elif [ -f "venv/bin/python3" ]; then
    PYTHON_BIN="venv/bin/python3"
fi

echo "Using Python: $PYTHON_BIN"
$PYTHON_BIN -c "
import cv2
import sys
try:
    print('Attempting to load YOLOv11 model: ${YOLO_MODEL_PATH} ...')
    net = cv2.dnn.readNetFromONNX('${YOLO_MODEL_PATH}')
    print('[OK] YOLOv11 model successfully loaded by OpenCV DNN module!')
except Exception as e:
    print(f'[ERROR] Failed to load YOLOv11 model: {e}')
    sys.exit(1)
"

echo "=== [Gigi Model Upgrade] Complete! ==="
echo "To launch the upgraded LLM server, run:"
echo "  sudo ./llm_server.sh"
echo "=============================================================================="
