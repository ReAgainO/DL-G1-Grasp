# B-1 车道 FINDING — 进路时钟预算一致性（26 s 硬绑 vs 32 s 相位预算）

TASKID `20261008-125638-qoder-d266d3a9`（第三轮），节点 worker00039 / group4。
车道目录 `/data/group4/20261008-125638-qoder-d266d3a9/B1_clock/`。

## verdict

**根因确认（读码得到，不是猜）**：同一个 APPROACH 相位有两套互不相认的时间预算——
`sonic_grasp.py:244` 在开 `--clearance-branch-servo` 时取
`BranchExecution.approach_timeout_seconds = 32.`（`branch_execution.py:12`），
而 `clearance_approach.py:26` 把 `update()` 的入参硬绑成 `elapsed>26` 就 `raise`。
⇒ 32 s 的**软超时**（会写 `fail_reason`）永远轮不到，26 s 的**硬断言**先把 run 炸成
`rc=1、无 result.json`。旧参考在 15.578 s 过净空 ＋ 6 s 过渡＝占 21.578 s 所以从没碰到；
新 ARDY 参考过不了净空，于是每次都撞在 26 s 上。

**补丁做的事**：把调用方的预算传进脚手架（`time_limit_s=approach_timeout`），
默认值仍是 26 ⇒ 未打这条调用的任何调用者行为逐字不变；另加 `8<=time_limit_s<=60` 断言。
**没有动 20 道成功门、没有动任何静态阈值、没有把 26 或 32 调大**——只是让两者一致。

**惰性证明（正对照）**：S1000（未打补丁）vs B1_clock（打补丁）同配置三格
`a35_02_05 / d50_00_00 / c20f_00_00`，各 2371 叶子中仅 61 个不同，
其中 58 个是 `execution_cycle_latency/*` 计时叶子；剩下 3 个「非计时」差异全部是
(a) 含车道名的路径字符串 `selected_source_npz` / `source_npz`、
(b) `runtime_stamp.library_sha.clearance_approach`（**本来就该不同**，它哈希的正是被我改的那个文件）。
三格 `success` 相同、`hold_min_lift_m` **逐位相同**。⇒ 对能通过净空检查的格，补丁物理惰性。

**效果证明（处理组）**：新 ARDY 参考的 4 格从「炸掉无数据」变成可测量：
`e35n_00_00`、`e35n_12_08` → `fail_reason="approach native branch settling timeout"`（正规失败记录）；
`e35n_04_00`、`e35n_08_04` → **走完全相位** `SETTLE→…→SETTLE_RELEASE`、`fail_reason=None`、
`success=False`、`hold_min_lift_m=-7.6e-05 / -9.2e-05`（方块全程留在桌上）。
⇒ 第一次拿到「新参考到底走到哪一步」的可机读答案：**它能走完流程但抓不起来**，
不是崩在接线上的假无数据。

## 判据与方法

- 只读 `result.json` 的 `success` 与 20 道 `gates`；`rc` 不是成功位；`-1.0` 与 `1e9` 是无样本哨兵。
- 车道 fork 自 S1000 的 `rep`（逐字节基线，sha 记录在文末），fork 后清掉复制来的 167 个格目录保证名字新鲜。
- 三处锚点各断言命中 1 次才落笔；打完 `ast.parse` 通过；diff 原文入库
  `B1_clock/raw/b1_clearance_approach.diff`（11 行变更）与 `b1_sonic_grasp.diff`（2 行变更）。
- 比较器是父会话自己写的尺子 `S1000/agg.py compare`（忽略族只有计时/路径/加载时间三类，写在输出头部）。

## 凭证

- 基线 sha：`clearance_approach.py` `94356a8088bd16da207caec9d220980cd4be335fb421ed7a4109274dfb449020`，
  `sonic_grasp.py` `0e0435b66da9b9b5d56092246a0deda23c6b38fdac01f7d39e5a8496f14148b9`
- 打补丁后：`clearance_approach.py` `d75717fe31f814b9d36a5059052b1dedbb7546a21d7bd1055c4f4938c5354cdd`，
  `sonic_grasp.py` `1e2a8edd9667bc62ec7f50898a775c87af54e638bdb1ba43723cbf2334c09c74`
- 环境：mujoco 3.2.7 / numpy 1.26.4 / onnxruntime 1.23.2；`ulimit -v 16 GiB`、`nice 19`、
  `taskset` 88..127（扫描占 8..87，互不打架）；CPU-only，未占 GPU，未打占卡票据。
- 冻结 flag 表与 S1000 同一件（sha `31d3d77548e91ce6…`）。

## 下一步（本车道内）

1. 用打过补丁的 build **重跑整个 e35n 层（100 格）**，把「新 ARDY 参考」第一次变成有分母可报的层
   （已在跑：`B1_clock/drive_e35n.sh`，20 道并行，核 88..127）。
2. 若 100 格里出现 `success=True`，那才是 ARDY 新生成链的第一次成功；否则如实报 0/100 并给出
   失败相位分布（净空超时 / 走完流程但抓不起 / 静态全拒）。
3. 只有到这一步之后，A（把 ② 的闭合姿态编译成 ARDY 末关键帧）才有意义：现在我们知道
   新参考是「能走完、抓不起来」，而不是「跑不完」。
