# Kimodo / ARDY Motion Integration Delivery Report

- 执行方：TRAE / 本地工作区 `/Users/bytedance/sonic_bridge`
- 日期：2026-10-03
- 范围：当前 MuJoCo 方块场景、双来源 SONIC 接入、物理抓取 baseline

## 一、结论

Kimodo 和 ARDY 的 36 列输入均已通过 loader、640 维窗口和 SONIC
generated-motion 运行链；两者固定右臂写入均为 0。旧 CSV 并非针对当天
新建的方块场景，运行 `success=False` 不属于接入失败。

当前场景的 keyframe 物理抓取 baseline 已导出为 900 x 36 CSV 和完整
manifest。正例成功、无握力负例失败；未使用 weld、adhesion 或方块位姿写入。

## 二、操作步骤

1. 为 `run_grasp.py` 增加仅限成功 keyframe 正例的 CSV/manifest 导出。
2. 新增 baseline 资产校验模块及单元测试。
3. 新增输入契约、复现说明和 quick/full 自动验收入口。
4. 修订阶段 8，将 integration smoke 与 scene-conditioned grasp 分开。
5. 实跑 baseline 生产、四案例完整验收、52 项单测和离屏渲染。

## 三、实测证据

### 场景与资产

| 项目 | 实测 |
|---|---|
| MuJoCo 模型 | `nq=57`, `nv=55`, `nu=43` |
| 场景对象 | robot、table、free-joint red cube 均存在 |
| equality constraints | `neq=0` |
| baseline CSV | `900 x 36`, 50 Hz, 18.0 s |
| baseline CSV SHA-256 | `c9a7f91eac95b1e699ba9838832ad5323c6d24894ac743188bd831f9a796297c` |
| manifest SHA-256 | `ed2ab9562dc39f3896bdd126461d9839c00b2f00e4e922540dc39fd4873c64f6` |
| baseline loader 回读 | 900 帧，joint-limit clipping 0 |

### 物理抓取

| 案例 | success | 接触体 | 抬升 | clearance | lift contact |
|---|---:|---:|---:|---:|---:|
| keyframe positive | true | 2 | 0.0954 m | 0.1274 m | 4.000 s |
| keyframe `--no-grip` | false | 0 | 0.0000 m | 0.0319 m | 0.000 s |

正例接触体为 `right_hand_thumb_2_link` 和
`right_hand_index_1_link`，峰值法向力 `4.211 N`。

### 双来源 SONIC smoke

| 来源 | 窗口数 | 变化数 | fixed override | fixed PD | grasp |
|---|---:|---:|---:|---:|---:|
| Kimodo `walk_s0` | 100 | 99 | 0 | 0 | false |
| ARDY `final_s0` | 100 | 99 | 0 | 0 | false |

`grasp=false` 是预期的场景不匹配结果；接入验收依据是动态窗口推进、无固定臂
路径和运行完成。

### 测试与渲染

- `.venv310/bin/python -m unittest discover -s tests -v`：52/52 通过。
- `tools/accept_motion_delivery.py`：quick PASS。
- `tools/accept_motion_delivery.py --full`：full PASS。
- 离屏渲染：6 张 640 x 480 PNG，共约 968 KiB，位于
  `server_reports/assets/g1_cube_grasp_baseline_render/`。
- 6 帧像素标准差范围 `30.487–32.735`，每帧独特色值数量
  `2946–3093`，均为非空图像。

## 四、失败项与原因

- 内置图片查看接口上传 `frame_00005.png` 失败：
  `Upload failed: system error: Failed to upload file`。本地 6 张 PNG 均存在并
  已计算 SHA-256，但本轮未完成人工画面检查。
- 尚无 Kimodo/ARDY 为当前 scene hash 生成的专项轨迹，因此不能声明任一方法
  已在当前场景完成生成式抓取。交付的 keyframe CSV 明确是 ground truth，
  manifest 中 `sonic_closed_loop_replay_validated=false`。

## 五、下一步建议

Kimodo 和 ARDY 方法组应按 `MOTION_INPUT_CONTRACT.md` 生成各自的新轨迹及
scene-conditioned manifest。收到后分别执行 full smoke、物理正例和
`--no-grip` 负例，并将 `sonic_closed_loop_replay_validated` 只在实测成功后
改为 true。

## 六、复现方法

```bash
.venv310/bin/python tools/accept_motion_delivery.py
.venv310/bin/python tools/accept_motion_delivery.py --full
.venv310/bin/python -m unittest discover -s tests -v
```

baseline 重新生成和 macOS viewer 命令见
`MOTION_DELIVERY_REPRODUCTION.md`。
