# SEARCH-NOTES.md — 核实过的禁引用项与证据（ws3_static）
- 父 TASKID: 20261008-221515-qoder-03c4673f；节点 worker00039
- 核实时间: 2026-10-08 22:16-23:15（本地）；核实方式：一手页面抓取（WebFetch/WebSearch），非二手转述
- 用途：任何报告/回传引用下列条目时，按"禁引"栏执行

## 1. DexUMI —— 禁写"在 Unitree Dex3-1 上验证"
- 一手证据: https://dex-umi.github.io/（2026-10-08 抓取）。页面原文的手硬件描述为 "XHand and Inspire Hand"；全部评测、消融与成功率均仅基于这两款手；
  **零次**提及 Unitree Dex3-1（原文核查：页面无 "Dex3" / "Unitree" 组合出现）。
- 禁引: 任何" DexUMI 的 X/Y/Z 结论可用于 Dex3-1"或"DexUMI 用 Dex3-1"的写法。
- 可用: DexUMI 的"人手即接口（佩戴式手外骨骼）+ 视觉合成"方法论可作类比（与硬件无关的层面），引用时须写明"其硬件为 XHand/Inspire，与 Dex3-1 非同构"。

## 2. GEX（arXiv:2506.04982）—— 禁写"用 Dex3-1"
- 一手证据: https://arxiv.org/abs/2506.04982（2026-10-08 抓取）。摘要原文：自研 "GX11 tri-finger anthropomorphic hand (11 DoF)"，配 "modular 3D-printed finger designs"、"independent joint motors across all 23 DoF"；
  **零次**提及 Unitree Dex3-1。
- 禁引: 任何"GEX 的抓取配方在 Dex3-1 上适用/已验证"的写法。
- 可用: GEX 的"模组化 3D 打印指节 + 全关节独立驱动"设计取向可作对 Dex3-1 欠驱动/关节数差异的讨论素材，但须显式标注硬件不同构。

## 3. 本节点不可实跑 Isaac 系（背景性约束，防止他人误排产）
- unitree_sim_isaaclab 要求 Isaac Sim 4.5/5.x + RTX GPU（其 README.md:11,15,127 明示）；本节点为摩尔线程 MUSA、无 CUDA、无 Isaac ⇒ 该仓全部结论只能静态引用，禁止排"在 worker00039 上跑 unitree_sim_isaaclab"的实验。
- 同理 HomieRL（Isaac Gym Preview 4）亦不可实跑（其 README Prerequisites：Isaac Gym 4.0 + NVIDIA GPU）。

## 4. lerobot 的 SONIC 复现件是"decoder-only"（防过度引用）
- src/lerobot/robots/unitree_g1/controllers/sonic_whole_body.py:17-24 原文："Pure-Python/ONNX re-implementation of the *decode* half … The encoder is intentionally absent"。
- 禁引: 把它当"完整 SONIC 栈"或"可替代本组 sonic 仓的端到端方案"；它是 token(64D)+proprio 历史 → 29 关节残差的解码器（CONTROL_DT 0.02=50Hz，文件 :53）。
- 权重位置: HF "lerobot/sonic_decoder"（huggingface.co 本节点不可达；hf-mirror.com 可达，需走镜像）。

## 5. 引用本组尺寸曲线时的强制出处
- "20 mm 0/250、25 mm 4/150（2.7 %）、35 mm 255/392（65.1 %）、50 mm 60/96（62.5 %）"须引：
  /home/group4/group4_dasc7606c/reports/20261008-125638-qoder-d266d3a9-report.md:12（同口径另见 reports/20261008-214754-codex-1ac8adb9-report.md:24）
- 禁写"这四档来自某个公开方案"——它们是本组自有固定网格实验的描述性比例（125638 报告原文用词："均是该固定网格与 build 的描述性比例"）。

## 6. 顺带核实（可用，非禁引）
- HF 仓 lerobot/unitree-g1-mujoco 的 dex3 模型文件为 assets/scene_hands_cameras.xml（=assets/g1_29dof_with_hand_cameras.xml 家族；nq=50/nu=43，29 body 保持原 DDS 序）；其 README 明说 "The existing make_env() entry point, 29 body motor commands … are preserved"——手指不进入 29-body 指令通道，与 lerobot unitree_g1.py:295-298（action=29 关节）互证。
- xrteleop 的 Dex3 是每手 7 电机（robot_hand_unitree.py:27），与本组 Dex3-1 一致（非 11 DoF 类）；左右手 SDK 关节序不同（右手 index/middle 互换，robot_hand_unitree.py:222-229）——写报告引用关节序时勿按"左右对称"想当然。
