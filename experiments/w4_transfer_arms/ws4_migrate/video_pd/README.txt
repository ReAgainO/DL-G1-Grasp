W4b2 PD 臂视频（仅 success=True 格；判据=rep_ext_pd/rep/out/<cell>/result.json）
====================================================================
1) W4b2_pd_a35_00_10.mp4
   格: a35_00_10 (35mm, x=0.266000 y=-0.114000, FACE=0)
   S1000 基线: 近成功(仅 no_robot_table_contact_full_task 红, lift 129.4 / slip 3.83, fb=0)
   PD(100,10,arm0.1): 全绿成功 lift 128.9mm / slip 2.91mm (fb=0)
   745 帧 @12.5fps (~59.6s), 960x720, h264 crf20
   sha256 917f2d80b1413c3e84f14c146a9184ce14c7601df27d4dbf835e260c2562984e
2) W4b2_pd_b25_02_06.mp4
   格: b25_02_06 (25mm, x=0.270200 y=-0.127600)
   W4a 基线(rep_base): 近成功(仅桌子门红, 121.5 / 3.69, fb=0)
   PD: 成功 131.7mm / 2.25mm (PD 侧 fb=18, 参考滤镜介入, 类别级对照)
   746 帧 @12.5fps (~59.7s), 960x720, h264 crf20
   sha256 b72dc55688e90dd30f803a14876ab1281f53154c5bb13582e2de98e4e286cc9c

渲染方法(本次独立打通; 参考只读 v4b_render_shard.py 的 FK 回放原则)
- 逐帧 d.qpos=qpos[i]; d.qvel=0; mj_forward; render — 不调用 mj_step(物理不步进)
- 模型: rep_ext_pd/rep/out/<cell>/scene.xml (含 g1_free_grasp.xml, 即带 armature=0.1 的 PD 模型)
- 相机: MjvCamera lookat=[0.280,-0.110,0.780] distance=1.10 azimuth=-125 elevation=-18, 960x720
- osmesa: LD_LIBRARY_PATH=/data/group4/20261008-220500-codex-6c40bf04/lib (指向 libOSMesa.so.8 软链), MUJOCO_GL=osmesa
- 抽帧 step=2 -> 输出 --framerate 12.5; 编码 imageio_ffmpeg v7.0.2 (envs/render)
- 脚本 /tmp/ws4b2_render.py (本机草稿 worker-ws4b2/ws4b2_render.py)

QA
- 解码帧数 == ceil(len(qpos)/2) 精确一致 (745/746)
- 抽帧 nonblack=1.000 / mean 79-83 / std 40-47 (每格 4 帧)
- frames_* 目录保留为中间证据
