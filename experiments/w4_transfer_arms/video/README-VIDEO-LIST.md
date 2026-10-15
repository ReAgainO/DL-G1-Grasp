# 本任务自产演示视频清单（16 段）

- TASKID: 20261008-221515-qoder-03c4673f；生成方：qoder 子代理（含 runtime_stamp 的渲染管线）
- 路径前缀：`/data/group4/20261008-221515-qoder-03c4673f/`

## A. menagerie 复现（W1）—— ws1_menagerie/video/
| 文件 | 内容 | 判据状态 |
|---|---|---|
| e20_grasp_0.mp4 / e25_grasp_0.mp4 / e35_grasp_0.mp4 | 20/25/35mm 抓取失败例（释放即脱手） | 失败（设计内结论） |
| e20_negctl_0.mp4 | 负对照（手指不闭合） | 预期失败 ✓ |
| e20_ideal_0.mp4 | 理想固连正对照 | 全判据成功（评测链证明） |
| smoke_e20_grasp_000.mp4 | 冒烟 | — |

## B. menagerie pads-only 变体（W1b）—— ws1_menagerie/pads_variant/video/
| 文件 | 内容 | 判据状态 |
|---|---|---|
| e50_tm_grasp_seed0.mp4 / e35_tm_grasp_seed0.mp4 | pads-only 失败例（斜楔滑穿） | 失败（机制已定量） |
| e20_ideal_selfcheck.mp4 | 正对照自检 | 成功（评测链） |

## C. 位置伺服臂（W4b2）—— ws4_migrate/video_pd/
| 文件 | 对应格 | 判据状态 |
|---|---|---|
| W4b2_pd_a35_00_10.mp4 | a35_00_10（35mm 近成功→全绿） | 35mm 新翻正（RV 已核） |
| W4b2_pd_b25_02_06.mp4 | b25_02_06（25mm 近→物理抓起，仅桌门） | 25mm 近成功 |

## D. 物理配方臂（W4c）—— ws4_migrate/video_phys/
| 文件 | 对应格 | 判据状态 |
|---|---|---|
| b25_00_00__phys.mp4 | b25_00_00 三件套开启 | 唯一 strict 翻成功格（15.25N→0） |
| b25_12_04__base.mp4 / b25_12_04__phys.mp4 | b25_12_04 同格 base vs phys 对比 | 对比演示（slip 改善） |

## E. 组合臂（W4e）—— ws4_migrate/video_comb/
| 文件 | 对应格 | 判据状态 |
|---|---|---|
| a35_00_15__comb.mp4 | a35_00_15（"从未抬起"→组合全绿） | 35mm 组合救活（父会话现读） |
| b25_00_00__comb.mp4 | b25_00_00 组合开启 | strict 保持翻转（143.4mm） |

## F. 登记引用（非本任务产物）
- e35n 成功合片（12 段旧成功 + 4 段新链成功）：`/data/group4/20261008-182000-qoder-7d11d1ae/ws4_video*/`（只读引用，勿搬运）

## 核对方法
```bash
find /data/group4/20261008-221515-qoder-03c4673f -name "*.mp4" | grep -vE "gr00t_repo|ws5_research/repos" | sort
# 应列出上表 16 段（不含 F 节引用项）
```
