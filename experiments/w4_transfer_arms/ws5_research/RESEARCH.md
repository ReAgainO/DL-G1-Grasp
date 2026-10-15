# RESEARCH.md — 外网检索：同类抓取问题的公开解决先例

- 任务: 20261008-221515-qoder-03c4673f / ws5 外网检索
- 背景问题: S4000 上 MuJoCo 跑 Unitree G1 + Dex3 抓 20-35mm 小方块，成功率极低（20mm 0/250、25mm 2.7%）；失败机制=撞飞/滑移/掌指穿模/握位偏差。
- 取证会话: 2026-10-08 22:16–22:26 (+0800)；取证时刻为本次会话分钟级记录，全过程见 steps-ws5.md（同目录 logs）。
- 检索主体: WebSearch + WebFetch；CSDN/GitHub API/arXiv/B站 用节点 curl -L 复核 http_code（节点 worker00039）。
- 纪律: 引用为逐字短摘录；“拿不到”一律注明；无编造链接。

## 0. 一句话结论

公开面里**没有**“G1+Dex3 抓 20mm 方块高成功率”的现成配方；但有 4 条高价值可迁移线：
(a) 同型号同引擎的 G1+Dex3 抓取全流程先例（漏抓根因=**闭爪动作没进控制**，执行窗口 5→25 步解决）；
(b) 官方 IsaacLab 栈的**夹爪 friction=200 锁死关节 / 闭爪行程 0.0223 vs 0.0245** 两个隐蔽坑（已有人定位+修好）；
(c) **Dex3-1 握小立方体（骰子）的成套参数**（kp=50、dampratio=1、力限±1.4/2.45Nm、预调 grip_qpos+残差动作、先 GRIP 课程）；
(d) MuJoCo 接触参数面（condim 4/6、friction 上调、solimp/.99、iterations 30-50、椭圆锥）——中文来源疑似 AI 汇编，需对照官方文档自证。

## 1. 条目表（31 条；含空结果与无效条目）

### A. 同款先例：G1/Dex3 + MuJoCo 抓取与握姿

| # | 链接/平台 | 取证时刻 | 问题 | 解法要点（含逐字摘录） | 可迁移性 | 一句话理由 |
|---|---|---|---|---|---|---|
| A1 | https://github.com/wge639286-debug/g1-dex3-act-grasping （GitHub API 直取） | 2026-10-08 22:22-22:24 | G1 右臂+Dex3 在 MuJoCo 抓白杯（示教→LeRobot ACT 闭环），策略抓不稳/不出手 | ①自适应三指抓握（G 键，基于接触）②成功判据“杯子最低碰撞点离桌至少 10 mm、无杯子/桌面接触，并连续保持至少 1.0 秒”③**关键**：逐字“执行窗口为5步时，ACT不断重新预测接近阶段，手指闭合动作总被留在预测序列的未来；改为执行25步后，闭合动作能够进入实际控制并完成抬杯。”④30 条示教/12,956 帧/25Hz/14D 状态动作/头部 RGB 480×848⑤10 个固定位置 10/10，最难位 ±2mm 抖动 10/10，平均成功 25.3s，平均抬升 18.5mm | 高 | 同型号同引擎、抓取物比我们大但流程完整；闭爪“假动作”归因与 25 步窗口可直接抄。 |
| A2 | https://github.com/Adithya191101/unitree-dex3-rl （GitHub API 直取） | 2026-10-08 22:23 | Dex3-1 三指把 cube/骰子稳定握在掌中（in-hand reorientation），初始握姿易掉 | 逐字：“Native MuJoCo position actuators (kp=50, dampratio=1), per-joint forcerange: thumb_0 ±2.45 Nm, all others ±1.4 Nm”；“ctrl = grip_qpos + action * action_scale”，“action = 0 holds the dice at the default grip position”，action_scale=0.25 rad（课程早期 0.08→0.15→0.25）；9 阶段课程第一阶段 GRIP 要求 eval 成功率 95% 才进阶；接触奖励（3 指 +0.1/2 指 +0.05）、掉落 -50；仓库带 `scripts/sweep_grip.py`（握姿参数扫描）与 `diagnose_hand.py` | 高 | 骰子≈16mm 与我们 20mm 方块同量级；“预调 grip 构型先验 + 残差动作 + 先握稳再操作”的完整参数集可直接试点。 |
| A3 | https://github.com/sixteenyao/home-robot （GitHub API 直取） | 2026-10-08 22:23 | 无手指 29dof G1 模型在 MuJoCo 里“抓取”怎么做 | 逐字：“G1 官方无带权重的抓取 RL;29dof 模型无手指,吸附是诚实方案”——用吸附约束（attach）代替手指接触；全身用 ETH CRL 官方 ONNX 策略；修复“策略用 Isaac Lab BFS 交错序、MuJoCo XML 是深度优先序，按关节名运行时重映射” | 中 | attach 可作为判定链路上限的透明对照基线；关节序重映射坑对任何策略迁移可复用。 |
| A4 | https://github.com/ondrakocman/i-am-robot-mujoco （GitHub API 直取） | 2026-10-08 22:23 | G1+Dex3 遥操作仿真 | MuJoCo WASM teleop（Quest3）；README 404（仅描述） | 低 | 生态存在证据，无可抄内容。 |

### B. 仿真栈公开坑：unitree_sim_isaaclab / lerobot

| # | 链接/平台 | 取证时刻 | 问题 | 解法要点（含逐字摘录） | 可迁移性 | 一句话理由 |
|---|---|---|---|---|---|---|
| B1 | https://github.com/unitreerobotics/unitree_sim_isaaclab/issues/132 （GitHub API 直取） | 2026-10-08 22:19-22:20 | VLA 策略抓不起方块、夹爪状态恒~0 | 逐字：“Stock config: friction=200.0 on gripper joints with tiny range ≈[-0.02, 0.024] rad.”；“Max PD torque ≈ stiffness × range ≈ 800 × 0.024 ≈ 19 Nm. Friction 200 ≫ that → joints physically locked”；“Symptom: ... gripper state stays ~0 regardless of commands”；“Fix that works for us: friction=200.0 → 0.0”；且“soft_joint_pos_limit_factor=0.9 caps close at ~0.0223 vs hard ~0.0245 ... Setting factor to 1.0 helps StackRyg grasp reliability.” 同 issue 还报：HF 数据集 ~50% 语言标签错、腕相机外参与训练分布不一致 | 高 | “闭爪但无夹持力”的最隐蔽根因清单；我们 Dex3 只要同源写法（actuator friction、soft limit factor）必须逐项排查。 |
| B2 | https://github.com/unitreerobotics/unitree_sim_isaaclab/issues/99 （GitHub API 直取） | 2026-10-08 22:19 | 夹爪状态换算范围前后不一致 | 逐字：docstring “[-0.02, 0.03] -> [5.6, 0]”与代码变量注释 “input range [-0.02, 0.024] / input_min=0.024 fully closed”混用；闭爪行程仅约 22–24mm 线性映射 | 高 | 20–35mm 方块下，任一端的范围混用都会让“差 2mm”变成稳定失败。 |
| B3 | https://github.com/unitreerobotics/unitree_sim_isaaclab （GitHub API 直取） | 2026-10-08 22:19 | 官方 IsaacLab 仿真栈复现 | 558⭐，pushed 2026-03-30；相关 issue：#119/#120 “fix dex3 RH”、#123 “dex3 obs functions device mismatch on Isaac Sim 6.0”、#108 “Challenges to be faced in sim2real deployment”、#110 unitree_lerobot eval_g1_sim 卡“Waiting to subscribe”（DDS） | 中 | dex3 官方支持仍在修补；复现前先读这批 issue 可省时间。 |
| B4 | https://huggingface.co/lerobot/unitree-g1-mujoco （WebFetch 直取 model card） | 2026-10-08 22:17 | LeRobot 里的 G1 MuJoCo 环境怎么用、有什么坑 | 逐字：“Choose the end effectors: ... `dex3` (default): ... 29 body + 7 joints per hand”；“Gripper `q` is in metres and `tau` is in newtons; each finger is limited to 20 N.”；“MUJOCO_GL=egl python -m unittest discover -s tests -v”；坑①“Run `python build_gripper_model.py --official-limits` ... it leaves approximately 5.88 mm between the supplied finger pads.”（官方 URDF 闭爪下限 −0.020m vs 仿真 −0.023m）坑②“This model update does not add finger actions to LeRobot's 29-body-motor `UnitreeG1` action schema.” | 高 | 我们用 lerobot 数据/动作空间时，“手指动作不在 action schema”与“闭爪行程/指垫间隙”两个坑会直接撞上。 |
| B5 | https://huggingface.co/lerobot/unitree-g1-mujoco/discussions （WebFetch） | 2026-10-08 22:22 | 该模型社区问答里有无 dex3/抓取线索 | **空**：页面 Discussions 仅 1 条 “Upload smpl_skeleton.npz”（LeRobot 维护者），无 dex3/grasp/gripper 讨论 | 空 | 社区没人在这个模型上问抓取；不要在此面继续挖。 |
| B6 | https://m.blog.csdn.net/2401_83634908/article/details/154072423 （CSDN，node curl 200） | 2026-10-08 22:25 | xr_teleoperate + unitree_sim_isaaclab 全流程复现记录 | conda(tv) 环境、pinocchio、televuer 证书、dex-retargeting、unitree_sdk2_python；Isaac Sim 4.5/5.0；docker build 实测 2078.7s；代理/--network host；报错“docker: Error response from daemon: could not select device driver "" with capabilities: [gpu]”（需 nvidia-container-toolkit）；`xhost +local:docker`；任务名带 Wholebody 才可移动操作；与真机同 DDS 便于数采 | 中 | 真实逐命令复现日志（含报错原文），IsaacLab 路线的前车之鉴。 |
| B7 | https://github.com/unitreerobotics/unitree_sim_isaaclab/issues/54 （GitHub API 直取） | 2026-10-08 22:20 | IsaacLab 4.5 Ubuntu 22.04 上官方示例任务启动崩溃 | 日志：`python sim_main.py --task Isaac-PickPlace-Cylinder-G129-Dex1-Joint` 崩溃；标题 “Base installation crashes on IsaacLab 4.5 Ubuntu 22.04” | 低 | 复现门槛证据；与我们的 MuJoCo 路线无关但说明官方栈不稳。 |

### C. MuJoCo 接触/摩擦/穿模调参（中文二手；标注 AI 汇编嫌疑）

| # | 链接/平台 | 取证时刻 | 问题 | 解法要点（含逐字摘录） | 可迁移性 | 一句话理由 |
|---|---|---|---|---|---|---|
| C1 | https://m.blog.csdn.net/gitblog_00750/article/details/157961515 （CSDN，node curl 200） | 2026-10-08 22:20 | MuJoCo 物体莫名滑动、摩擦失效 | condim 表：逐字“condim=4 | 4 | 6 | 包含扭转摩擦（软手指抓取）⭐⭐⭐⭐”；friction 三系数（静/动/滚动）+材质表（金属-金属 0.3-0.6、塑料-塑料 0.2-0.4）；solref[0] 推荐 0.001–0.1、solimp[0] 0.8–0.99；`<option cone="elliptic"/>`；priority 控制接触序；示例对比“滑移 12.7mm→0.8mm” | 中 | 滑移/接触不稳的一组可 A/B 参数面；内容是 AI 汇编（引用 mujoco doc 文件名），数值需回官方文档核对。 |
| C2 | https://blog.csdn.net/gitblog_01042/article/details/152445081 （CSDN，node curl 200） | 2026-10-08 22:21 | 抓取接触点少、摩擦失配、迭代不足 | 指垫改 capsule + 逐字 `<geom ... condim="6" friction="1.2 0.05 0.02" solimp="0.98 0.999 0.0001" solref="0.01 1.5"/>`；“迭代次数从10增加到50，接触力计算误差从0.8N降至0.1N”；宣称成功率 62%→94%（未验证） | 中 | 指尖几何+接触维度的具体改法；宣称值未独立验证，仅作起点。 |
| C3 | https://m.blog.csdn.net/gitblog_00487/article/details/151521145 （CSDN，node curl 200） | 2026-10-08 22:21 | 抓取滑落、姿态偏移、穿透 | `<default><geom friction="1.2 0.1 0.1" solimp=".99 .999 .0001" solref="0.01 1"/>`；`<option timestep="0.001" solver="CG" iterations="50" tolerance="1e-8"/>`；touch 传感器监看指尖力；逐字“物体穿透手指 | 求解器迭代次数不足 | 提高 iterations” | 中 | 给“穿模”一条直给的排查路径（iterations/时间步）；AI 汇编嫌疑同 C1。 |
| C4 | https://m.blog.csdn.net/gitblog_00603/article/details/155367890 （CSDN，node curl 200） | 2026-10-08 22:21 | unitree_mujoco 仿真器入门 | 官方 unitree_mujoco 的 C++/Python 安装与 config.yaml（robot/scene）；无抓取内容 | 低 | 环境面信息，不含抓取解法。 |
| C5 | https://m.blog.csdn.net/gitblog_00791/article/details/160675548 （CSDN，node curl 200） | 2026-10-08 22:18 | ——（标题诱饵） | **无效**：WebSearch 标题为“MuJoCo 机械臂抓取仿真不稳？指尖几何、摩擦与求解器怎么调”，正文实为 AWS CDK/NukeStack 内容（全文提取证实） | 无 | CSDN `gitblog_*` 号是内容农场，标题与正文不符，引用前必须全文核验（检索方法学坑）。 |
| C6 | https://m.blog.csdn.net/gitblog_01115/article/details/156403922 （CSDN，node curl 200） | 2026-10-08 22:24 | ——（标题诱饵） | **无效**：标题“如何在 LeRobot 中安装 Unitree G1 依赖并首次运行 MuJoCo 仿真遥操作？”，正文为 OpenJarvis（AI 记忆文件）内容 | 无 | 同上，第二例；凡 `gitblog_*` 标题先当嫌疑。 |
| C7 | https://bbs.csdn.net/weixin_29079643/article/details/100200534 （CSDN BBS，node curl 200） | 2026-10-08 22:24 | 宇树 G1 多指灵巧抓取“实战” | 叙述含 Dex3-1 力位混合闭环、g1_grasp_demo.py、握力 1.2–4.5N、±0.8mm 等数字；但 1/3 处收费墙，AI 生成痕迹重 | 低 | 数字无法核验，不作为依据；可当“Dex3 抓取”话题存在性证据。 |
| C8 | https://wenku.csdn.net/answer/anp162t1htzg （CSDN 文库，node curl 200） | 2026-10-08 22:24 | G1 视觉抓取整体栈 | AI 综述：RGB-D 位姿→VLA/策略→全身控制→sdk2；提及 MuJoCo、unitree_rl_gym、LeRobot 作为训练/仿真工具 | 低 | 泛化描述，无参数；仅作技术栈索引。 |

### D. 官方模型与“抓取构型先验”

| # | 链接/平台 | 取证时刻 | 问题 | 解法要点（含逐字摘录） | 可迁移性 | 一句话理由 |
|---|---|---|---|---|---|---|
| D1 | https://github.com/google-deepmind/mujoco_menagerie/blob/main/unitree_g1/g1_with_hands.xml （GitHub API 直取） | 2026-10-08 22:24-22:25 | 官方 G1+双手模型的执行器/接触参数基线 | 取证行：`<option integrator="implicitfast"/>`；`<joint armature="0.01" frictionloss="0.3"/>`；`<position kp="500" dampratio="1" inheritrange="1"/>`；手掌/三指碰撞体为整手 mesh（class collision），**全文件唯一显式接触参数**是足底 `<geom type="sphere" size="0.005" priority="1" friction="0.6" condim="3"/>`——即手指接触沿用 MuJoCo 默认（condim=3、无扭转维度） | 高 | 官方模型手指接触“没调过”；我们给 20mm 方块实验显式指垫 condim=4/6 + 更高 friction + 更硬 solimp 就有了对照基线。 |
| D2 | https://arxiv.org/abs/2410.24185 DexMimicGen（arXiv export API 200） | 2026-10-08 22:24 | 数据瓶颈：示范太少，抓取构型覆盖不足 | 逐字：“data acquisition is a major bottleneck ... automated data generation”；从少量人类示范自动生成数千条双臂灵巧操作数据（模仿学习范式） | 中 | “从人类/示教数据挖掘抓取段并放大”的公开标杆；可指导我们把已有遥操数据加工成闭爪先验。 |
| D3 | https://m.blog.csdn.net/yorkhunter/article/details/154736169 （CSDN） | 2026-10-08 22:18（仅搜索面呈现） | DexMimicGen 中文解读 | 未直取正文（只在搜索结果中出现）；记录为“搜索面可见、未取证正文” | 低 | 诚实标注：本条未直取，不作引用依据。 |

### E. ARDY / SONIC（公开话题存在，但抓取相关性为空）

| # | 链接/平台 | 取证时刻 | 问题 | 解法要点（含逐字摘录/为空证据） | 可迁移性 | 一句话理由 |
|---|---|---|---|---|---|---|
| E1 | https://arxiv.org/abs/2607.08741 + https://research.nvidia.com/labs/sil/projects/ardy/ （搜索面） | 2026-10-08 22:20 | ARDY 是否含抓取解法 | **为空**：ARDY=NVIDIA“Autoregressive Diffusion with Hybrid Representations”交互式**人体运动生成**（33ms 实时动捕驱动）；检索面（WebSearch×2、hyper.ai/techwalker 中文稿）无任何 Dex3/抓取/方块内容 | 无 | 名字相关的公开话题存在，但与抓取无交集；记录为空。 |
| E2 | https://arxiv.org/abs/2511.07820 + https://m.blog.csdn.net/v_july_v/article/details/156147131 （搜索面） | 2026-10-08 22:20 | SONIC 是否是抓取方案 | **为空/低**：SONIC=NVIDIA 人形**全身运动追踪**控制器（VR 数采→微调 VLA 做 loco-mani，低层 MLP）；不涉及手部抓取参数 | 无 | 公开话题存在但解决的是全身控制，非抓取。 |

### F. 中文社区实操面（B站/知乎/博客园）

| # | 链接/平台 | 取证时刻 | 问题 | 解法要点（为空证据） | 可迁移性 | 一句话理由 |
|---|---|---|---|---|---|---|
| F1 | https://api.bilibili.com/x/web-interface/view?bvid=BV1HJf1BVEqg （B站 API，node curl 200, API code=0） | 2026-10-08 22:24 | B 站有无“G1 抓取失败复盘”技术内容 | **为空**：view API 可达，样本视频《人形机器人如何学习：宇树 G1揭秘》（196 播放）为 RL 训练科普；两轮 WebSearch 检出 G1 相关视频均为开箱/演示/新闻（如 G1 Edu6 开箱 BV1xm3yzEE6N、Dex5 发布 BV1gCZbYJEMy），未检出抓取实操/失败复盘 | 空 | 该面在本次检索中无技术向内容；注意 www.bilibili.com 视频页 200 但页面无静态 title（JS 渲染），建议用 view API 取证。 |
| F2 | https://zhuanlan.zhihu.com/p/1897200096430518846 等（知乎，node curl） | 2026-10-08 22:23 | 知乎上的 G1 抓取/IsaacLab 实操 | **不可达**：`zhihu_code=403`（列于可达性纪律一致）；搜索面可见多篇（Isaac Lab 遥操作与模仿学习、灵巧手 awesome 列表 1966166542610838718），但正文 403 无法取证 | 空 | 知乎只能当索引，不能作为引用源。 |
| F3 | https://www.reddit.com/r/robotics/search/?q=unitree+g1+mujoco+grasp （Reddit，node curl） | 2026-10-08 22:23 | Reddit 上的同类讨论 | **不可达**：`reddit_code=000`（连接失败）；零收录 | 空 | 与可达性纪律一致，放弃该面。 |
| F4 | https://www.xiaohongshu.com / https://www.linkedin.com （node curl） | 2026-10-08 22:23 | 小红书/LinkedIn 内容 | 根域返回 200，但**无内容型命中**（无站内检索结果、无文章可取证）；记为“不可达/零收录”（与纪律一致，200 仅为首页） | 空 | 诚实记录：根域可达 ≠ 内容可达。 |
| F5 | https://www.cnblogs.com/quantoublog/articles/19190624 （博客园，node curl 200） | 2026-10-08 22:25 | 博客园上 G1 内容 | 平台可达（45KB，标题“【教程】宇树强化学习框架unitree_rl_gym完整部署流程(更换IsaacLab)”）；但站内检出的 G1 文章均为 RL 运动控制/部署（unitree_rl_gym、IsaacGym），**抓取实操为空** | 低 | 博客园 G1 面=运动控制内容，无抓取解法；记录为空。 |

## 2. 可达性实测汇总（每站实际响应）

| 站点/接口 | 出口 | 实际响应（2026-10-08 22:16-22:26 +0800） | 结论 |
|---|---|---|---|
| m.blog.csdn.net（-L 跟随） | 节点 curl | 首次 200（final=blog.csdn.net）；连续请求随机被 521 JS 挑战（约 1/2 命中），UA+sleep 重试 3 次内可取 | 半可靠，需重试器 |
| blog.csdn.net 直连 | 节点 curl | 521 | 不可直取 |
| m.blog.csdn.net → blog.csdn.net | WebFetch 出口 | 301 → 521 | WebFetch 拿不到 CSDN 正文 |
| api.github.com（未认证） | 节点 curl | 200（注意 60/h 限流） | 稳定 |
| raw.githubusercontent.com | 节点 curl | 000（不可达） | 改用 api contents + `Accept: application/vnd.github.raw` |
| huggingface.co 页面 | WebFetch | 200（model card 全文取到） | 稳定 |
| huggingface.co/api（节点） | 节点 curl | 000 挂起（需 --max-time；曾致后台任务超时） | 用 WebFetch 代替 |
| export.arxiv.org | 节点 curl | 200 | 稳定 |
| api.bilibili.com/x/web-interface/view | 节点 curl | 200，JSON code=0 | 可用（取标题/简介） |
| www.bilibili.com 视频页 | 节点 curl | 200 但无静态 title | 建议用 view API |
| zhuanlan.zhihu.com | 节点 curl | 403 | 不可达 |
| www.reddit.com | 节点 curl | 000（连接失败） | 不可达 |
| xiaohongshu / linkedin 根域 | 节点 curl | 200（仅首页，无内容命中） | 零收录 |
| cnblogs.com | 节点 curl | 200 | 稳定 |

## 3. 对我们的行动建议（按优先级）

1. **先排“闭爪假死/行程不足”**（对应 20mm 0/250 的第一嫌疑）：
   - 查我们 Dex3 MJCF/actuator：手指关节 `frictionloss`/阻尼、position 执行器是否含 friction 字段（参照 B1 的 friction=200 案例逻辑：PD 力矩上限 ≈ stiffness×行程），以及闭爪位是否可达“指垫间距 < 20mm 且有余量”（B1/B2/B4）。
   - 用“闭爪后指垫净距、接触力总和、接触点切向速度”三条量做日志（A1 仓库有现成 slip 诊断实现：`finger_cup_contacts`/切向速度用 `mj_contactForce`+`mj_jac`）。
2. **接触参数网格实验**（滑移/撞飞的直接对策）：指垫 geom 显式 `condim=4`（软指扭转）或 `6`、`friction` 0.6→1.2~2.0、`solimp=.99 .999 .0001`、`solref="0.01 1"`、`iterations` 10→30~50、可选 `cone="elliptic"`；来源 C1-C3 为 AI 汇编，**须自行 A/B 验证**。
3. **握姿先验（抓取构型）**：以 A2 的参数为模板（`kp=50, dampratio=1`、力限 ±1.4/2.45Nm、`grip_qpos + 残差`、先 GRIP 再操作），用 `sweep_grip` 思路对我们的方块扫“预调闭爪 qpos”；从已有遥操/LeRobot 数据里挖“首次接触后 qpos 冻结段”作为闭爪目标（D2 范式）。
4. **若走 IL/ACT 路线**：执行窗口 ≥25 步（A1 的直接教训）；在 MuJoCo 里注意 LeRobot 的 action schema 未含手指动作（B4），需自扩展或绕过。
5. **识别器**：C5/C6 两例证明 CSDN `gitblog_*` 标题不可信；任何引用先全文核验。

## 4. 空结果与不可达记录（汇总）

- ARDY（E1）：公开话题存在（人体运动生成），抓取内容为空。
- SONIC（E2）：公开话题存在（全身运动追踪），抓取内容为空。
- HF lerobot/unitree-g1-mujoco discussions（B5）：仅 1 条 smpl 上传讨论，抓取问答为空。
- B站（F1）：API 可达，未检出“G1 抓取失败复盘”技术向内容。
- 知乎（F2）：403；Reddit（F3）：000；小红书/LinkedIn（F4）：根域 200、内容零收录。
- 博客园（F5）：平台可达，G1 内容全为运动控制，抓取为空。
- CSDN 两条标题诱饵（C5/C6）：正文与标题不符，判为无效来源。
