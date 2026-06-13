#!/bin/bash
cd /home/orangepi/Code/gigi/Resources/rknn-llm/examples/rkllm_server_demo/rkllm_server/
/home/orangepi/Code/gigi/.venv/bin/python3 flask_server.py --rkllm_model_path /home/orangepi/Code/gigi/Resources/qwen2.5_3b.rkllm --target_platform rk3588
