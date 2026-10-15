# sonic_bridge

第一版 Sonic PyTorch bridge 骨架：

- 不走官方 C++ / TensorRT
- 自己写 Python/PyTorch 推理入口
- 先支持 G1 + MuJoCo
- 先按 observation_config 搭接口，再逐步接真实 checkpoint

## 运行

```bash
cd ~/group4_dasc7606c/sonic/sonic_bridge
python runners/run_sonic_mujoco.py --config configs/sonic_g1.yaml