# 冻结批次的独立只读复审

## 范围与证据分层

本次只读检查更新后的 `batch_runner.py`、`execute_batch.py`、`batch_plan.py`、`render_batch.py`、`audit_batch.py`、`summarize_batch.py`、`PROTOCOL.md` 及本地缓存的 AGENTS §17。没有 SSH、没有运行代码/仿真/渲染，也没有更改冻结的物理源文件。以下结构与控制结论属于**源码审计**；4个预检、数组逐项一致、53.12秒视频和首格 A000 通过审计等属于主代理报告的**运行时验证**，我未独立重跑或从服务器复核。

本地 §17 快照要求所有会进入报告/下游引用链的 JSON/CSV/NPZ 产物自带 stamp，至少含模拟器版本、绝对解释器路径、Python版本、模型SHA、场景生成脚本SHA、库/权重SHA及dt；缺项产物必须明确视为未盖章，不得引用数字。当前正式 `result.json`、`trajectory.npz`、`reference.npz`、`execution_plan.json`、`episode_contract.json` 中均有运行戳；`trajectory.npz`/`reference.npz` 以 `runtime_stamp_json` 保存。其核心字段符合此最低要求，且 execution stamp 另含源脚本/规划器、SONIC模块与ONNX权重、ARDY源、asset-manifest SHA、计划SHA、模型XML SHA、内存碰撞/惯量指纹及 dt/求解参数。D-C 与消融比较必须限定到锁定的 MuJoCo 3.2.7 版本/当前参数族；没有第二 MuJoCo 版本，不可上升为普遍物理因果结论。

## 仍需报告或汇总披露的限制

1. **未盖章诊断文件的引用边界。** `contact_frames.json` 是裸列表、`planning_refusal.json` 没有 `runtime_stamp`。按 §17，只能作为保留的未盖章原始诊断；最终结果不得把其中数值当事实引用。可引用带 stamp 的 `result.json` / `trajectory.npz` 字段，并注明接触诊断未盖章。对 planning refusal，正式带戳 `result.json` 与轨迹中的 `PLAN_REFUSED_SAFE_HOLD` 证明的是拒绝后的安全站立，不是抓取路径/失败抓取。

2. **聚合报告戳尚未落入当前汇总源码。** 当前审阅的 `summarize_batch.py` 生成的 `summary.json` 没有聚合 `runtime_stamp`，`REPORT.md` 仅有 manifest SHA；`audit_batch.py` 输出 MuJoCo/Python/解释器、manifest和审计脚本SHA等分散字段，也没有统一聚合戳。最终报告应附冻结 manifest SHA、正式源SHA、环境/版本和结果引用所用stamp；如对聚合物二次运行汇总器，也把汇总器本身SHA和汇总时间/输入清单写入聚合元数据。若主代理之后仅补总结器，请保留物理源冻结身份。

3. **stamp交叉核验的语义比名称窄。** `audit_batch.py` 验证了 result stamp 的 MuJoCo 版本、result模型SHA与落盘XML一致、trajectory 内戳等于 result 戳，并核配置、原生几何和门一致性；但当前 `runtime_hashes_verified=True` 没有表示它比较了 `episode_contract.runtime_stamp`、`execution_plan.json`、`reference.npz`、`plan.json` 的所有 stamp/哈希。报告应把该字段解释为“result/trajectory主链及XML核验通过”，不要夸大为所有产物两两一致。

4. **超时子类保留在逐格状态，不在现有汇总文字中。** runner 已为 planning/physics/render 的非零退出码分配 `planning_timeout`、`physics_timeout`、`render_timeout` 等 subtype，stage 记录也保留退出码与日志。当前 summarize 输出的终态仍合并在 `infrastructure_error`，`inspect_trial` 没有把 `infrastructure_subtype` 搬入summary；报告如需按超时区别统计，须从原始 `state/<ID>.json` 显式汇总。无论如何，timeout不属于物理失败，视频错误也不应覆写物理分类。

5. **数值的线程/资源记录分布在多处。** 当前 runner 固定最多8工人、各绑2核，并继承数值线程环境为1；renderer 的 LP_NUM_THREADS=2、ffmpeg线程=1，replay stamp记录 Mesa线程数和 CPU affinity；物理stage CPU pair在 state 中。它们没有全部并入每格 `runtime_stamp`。最终报告应同时引用 stage状态/日志和 replay 元数据，准确说明“数值/ORT 1线程、Mesa LP 2线程、每格2核”，不要笼统宣称都由物理结果戳直接证明。主代理报告这套限制已实测生效；本次只读审计没有自行观察进程或线程。

6. **安全与物理含义的边界。** 源码的 `no_cheats` 现在动态记录 base/object freejoint、`neq`/`nmocap`、cube actuator 数和外力；对象状态写入字段明确标成源码审计而非运行时钩子。执行循环内只写执行器控制量的源码检查是有价值的，但不能包装成运行时拦截证明。native mesh模式确实关闭三个人工球垫碰撞而保留原指骨与掌/腕几何；这证明配置，不证明每次掌面实际承载，也不代表几何与实机完全相同。路径筛选为20ms参考采样，不能证明动态运动全程无碰撞；此前原生整手轨迹在闭手前约10N接触是已知先例，故不宣称“碰撞完全干净”或“方块闭手前未受扰”。

7. **控制器与重力口径。** ARDY只用于单帧右臂姿态先验，之后是显式参考空间IK与SONIC v1.1全29维身体目标解码、腕参考修正及单独手指PD；不是原生ARDY全身时变闭环。NGF只去除右臂执行器的重力前馈，MuJoCo真实物理重力仍为 -9.81 m/s²；不可以写成“移除物理重力”。

## 对更新/运行状态的判断

- 上次发现的 1 GiB 父进程硬上限与 renderer 提升到4 GiB的冲突在当前源码中已统一为4 GiB；按代码继承关系，先前的 PermissionError 风险已消除。主代理报告的4个预检成功及完整解码视频提供了运行时补充证据。
- timeout现在记录阶段子类，但最终汇总还需保留并呈现该字段。
- A组是固定姿态/场景的确定性复现，不是随机泛化样本；D组改变机器人root初始x为−0.02m，场景方块世界坐标仍由XY/尺寸配置给定，不做方块反向移动；D-C应报告成有限配对试验。
- 规划拒绝的10秒安全站立输出需单列 `planning_refused` 与 `grasp_path_executed=false`。无论视频是否有效，都不计作实际抓取执行视频或物理抓取失败；物理成功率与视频交付率分开。
- 当前证据不能替代真实接触审计，不能把总体成功率合并到历史 H1b/v5/v6；A组复现数也不得表述为随机泛化率。

## 建议写进最终报告的限定语

“这些数据来自冻结的本批 MuJoCo 3.2.7 build、声明的模型/源文件和wholehand-v2 wrist-local-support门；门内结果仅说明本参数族的模拟基本抬升与保持。ARDY是姿态先验，非完整ARDY全身控制；NGF保留物理重力；几何激活不等于无接触接近、掌面承重或实机准确性。未盖章的 `contact_frames.json` 和 `planning_refusal.json` 不作为结果数字来源。”
