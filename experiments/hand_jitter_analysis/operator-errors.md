# 本次操作错误与修正（保留，不删除失败）

1. 服务器没有 `rg`：改用 `grep`；原始错误保留在任务 steps.md。
2. 第三轮未完成时过早调用分析，原始输出为：

```
ls: cannot access '/data/group4/20261009-170228-codex-fcd727b9/configs/wave3-done.json': No such file or directory
Traceback (most recent call last):
  File "/data/group4/20261009-170228-codex-fcd727b9/evaluate_wave.py", line 81, in <module>
    assert (R/'configs'/(wave+'-done.json')).exists()
AssertionError
```

3. 同一远程命令未在上述失败后停止，提前启动第四轮。短时间内第三、四轮工作进程重叠，超过任务声明的最多4个并发工作进程；所有进程仍被限制在本任务相同的80–87八个CPU上，不宣称全过程符合并发上限。
4. 确认第四轮每个进程的命令、工作目录和创建时间后，使用 `SIGSTOP` 暂停本任务的第四轮进程；第三轮done存在后再次逐一核验原PID身份，才使用 `SIGCONT` 续跑。未终止、暂停或清理他人进程，也未删改试验状态或日志。身份与暂停/续跑回执在 configs/wave4-paused.json、wave4-resumed.json。
5. 修正：新增 `launch_safe.py`，启动前检查本任务已有的仿真及渲染进程，发现未退出进程即拒绝启动下一轮。渲染使用同一任务级检查；后续命令使用短路执行。原已冻结的物理代码、输入、结果均未覆写。
6. 第三轮完成后才重新运行分析，生成唯一 wave3-evaluation.json；所有基线完整轨迹逐数组相等、处理前轨迹相等检查用于核验暂停/调度没有改变数值轨迹。

调度偏差与物理失败分开计数：A_lpf60是控制方案导致的物理失败，不能归入基础设施错误或删出结果。

7. 本机静态画图依赖检查显示 `ModuleNotFoundError: No module named 'matplotlib'`；未安装或修改本机环境，改用实际数字表格。
8. 第一次补充姿态/跟踪分析显示 `ModuleNotFoundError: No module named 'scipy'`，因为新分析程序没有加载已验证的只读 `plandeps310` 路径。仅在本任务的分析程序中补入该路径，没有改动任何环境或已有仿真源码。短路执行使后面的渲染未被错误启动；分析修正后重新执行。
