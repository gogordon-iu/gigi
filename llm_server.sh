#!/bin/bash
cd /home/orangepi/Code/gigi/Resources/rknn-llm/examples/rkllm_server_demo/rkllm_server/
python3 flask_server.py --rkllm_model_path /home/orangepi/Code/gigi/Resources/qwen2.5_1.5b.rkllm --target_platform rk3588
