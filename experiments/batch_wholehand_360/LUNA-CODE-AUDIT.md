# 独立只读代码审计：批跑改造

审计对象：`batch_plan.py`、`execute_batch.py`、`render_batch.py`、`batch_runner.py`、`make_trials.py`，并参考 `bootstrap_batch.py` 与 `LUNA-REPORT-CHECKLIST.md`。仅读代码，没有 SSH、运行预检/仿真/渲染、修改主代码或冻结 manifest。以下结论基于审阅时文件快照；正式批跑前须记录最终源文件与 manifest 哈希。

## 结论

试验池设计覆盖 300 主实验（A100、B100、C50、D50）与 60 配对消融（NGR/NWS/NGF 各20），独立 plan/physics rollout 与逐格轨迹回放的架构基本清楚。D 组在初始化时只将机器人 free-root 的 x 位置设为 -0.02 m，方块位置仍由场景配置固定；本代码路径没有用移动方块抵消站位变化。native mesh 模式关闭三个人工球垫碰撞，保留实际手指碰撞几何及掌/腕碰撞几何。计划拒绝另标 `planning_refused`，并有“不执行抓取路径”的安全站立记录；物理 rollout 的失败标为 `physics_failure`。

不过审阅快照存在一个会使录像阶段系统性失败的硬阻塞，另有超时分类和运行身份记录缺口。主 manifest 尚未冻结；修正后应重新审阅最终文件/哈希再启动正式360格。

## 必须先修

1. **渲染子进程地址空间上限冲突。** `batch_runner.py` 顶层将 `RLIMIT_AS` 的 soft/hard 都设为1 GiB（第5行），所有由它启动的 plan、physics、render 子进程继承该 hard limit；`render_batch.py` 又试图把 soft/hard 提升到4 GiB（第4行）。普通子进程不能越过继承的 hard limit，因此渲染启动将触发 `PermissionError`，令每个已完成物理格的视频阶段失败。并且这与 manifest 声明的4 GiB/job不一致。需在正式批跑前统一资源契约，例如 runner hard cap 设到允许的4 GiB，或 renderer 不再尝试提升限制，并做安全的小型预检。

2. **timeout 当前会折叠进 infrastructure_error。** `run_stage` 把 GNU `timeout` 的退出码写入 stage 日志；但 physics/plan 只要返回非零就抛一般 `RuntimeError`，外层统一归类 `infrastructure_error`（`batch_runner.py` 第60–78行）。超时常见的124/137因此无法在汇总中与程序异常分开。应从 stage 与退出码识别 timeout，并保留超时发生在哪个 phase；不能静默重试或改记物理失败。

## 重要但非阻塞的证据边界

- `execute_batch.py` 在native mesh分支把 `w.PADS` 的 `contype/conaffinity` 清零；执行几何集合按右手/腕/肘/肩实体碰撞 geom 选取，并以 active geom mask记录到 `episode_contract.json`。这支持“代码配置保留原手指/掌腕实体碰撞、关闭人工球垫”，但是否具体某次由掌面承载仍应看逐格contact记录，不能只凭几何启用宣称掌接触。
- no-gravity臂实际是 `gravity_arm_scale=0` 传给 SONIC torque计算的消融；MuJoCo物理重力仍保持启用。更新后的 `episode_contract.json` 已同时记录 `right_arm_gravity_feedforward_scale` 与 `physical_gravity_m_s2`，故应始终称“关闭右臂重力前馈”，不要称关闭物理重力。
- `no_cheats.free_base`、`free_object` 和 `object_state_writes_after_init` 是结果字典里的固定 `True/0`，并非运行时动态检查。代码审阅显示物理循环只写 `d.ctrl`，对象状态未被循环覆盖；`neq`、对象执行器和 `xfrc/qfrc` 有运行时字段。但报告最好把前三项标为源码/契约审计结论，而非自动检测结果，并可加上 freejoint 类型、对象 body actuator 映射的动态断言。
- 对象执行器计数当前按 `m.jnt_bodyid[actuator_trnid[:,0]] == cube_body` 统计；已比“所有free joint驱动器”准确，但应确认模型是否含非关节 transmission（其 `trnid` 可能为 -1）。稳妥实现应显式筛选 joint transmission 并核对 actuator/joint/body 名称。
- 每格 runtime stamp 包含 MuJoCo/Python版本、机器人与场景哈希、计划/脚本/SONIC模块及ONNX模型/ARDY源哈希、仿真dt与若干求解参数；独立 `manifest` 锁定其余批次源码 SHA 与 NumPy 版本。仍建议将每格实际 NumPy、SciPy 版本及执行器/运行参数加入 stamp，或明确引用不可变 manifest/runtime环境清单。当前由路径引用的 Python environment 本身不是内容哈希。
- `render_batch.py` 只恢复记录的 qpos/qvel，执行 `mj_forward`，不调用 `mj_step`；元数据标 `physical_steps:0`，因而是轨迹回放而非新仿真。拒绝路径有独立 `PLAN REFUSED - NO GRASP` 标题，safe-standing phase独立标注；不能把该10秒视频计成抓取执行或成功/物理失败样本的视频。
- 结果 ledger 的计划 ID 是固定360行，A组100个相同场景是固定条件复现，不是100个随机位置；B/C随机抽样、D与C复用位置/尺寸、仅改变root x。D-C和B20配对解释应按Checklist列出的配对四格报告，不能将60个消融并入300主实验成功率。

## 已核对的控制/统计路径

- `make_trials.py` 以固定 NumPy seed 生成B/C位置与尺寸，D从C拷贝同一位置/尺寸并用 `root_x_m=-0.02`；消融分别复制预先指定B000–B019。合计断言360个唯一 ID。
- `batch_plan.py` 先静态几何筛查，失败时 `execute_batch.py` 记录 `planning_refused` / `grasp_path_executed=false` 并走安全站立；通过后才生成动态参考。规划拒绝不是 physics failure。
- 执行器循环写入 `d.ctrl` 并调用 `mj_step`；没有看到对象 qpos、外力或 equality绑定注入。no-grip仍跑同一到达/闭合时间线但保持手指开位，适合作为机制消融；是否只改变预注册单变量需在逐格配置中复核。
- 每个 rollout有独立 `MjData`、初始根/对象场景与完整执行；渲染器是从该格记录状态回放，不能以同一视频复制充数。
- `batch_runner.py` 限并发为最多8个、每个绑定两个CPU core；各stage用 GNU timeout 包围，并有有限任务集合、状态与日志。其资源限制需按上方阻塞修复后再验证实际生效。

## 复核清单

正式运行前：修复并复核RLIMIT_AS；区分timeout与普通error；确认最终 `manifest.json`/`manifest.sha256` 与全部源码 SHA 一致；验证no-gravity-ff开关实际只关闭右臂前馈；逐格保留 planning refusal、physics failure、timeout、infrastructure error、video error 的互斥状态。运行后：按360个预定ID核对账本完整性、检查D/C场景只差root站位、检查每个真实trajectory视频的source hash与解码状态，拒绝视频仅标“无抓取路径”，并将视频交付完整度与物理成功率分开。
