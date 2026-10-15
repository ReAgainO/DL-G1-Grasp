# AGENTS.md — S4000 节点协作规约（强制）

**如果你是自动化代理（Qoder / Codex / ZCode / Kimi Code / 任何 CLI agent），读到本文件即代表你接受本规约。在本服务器上的一切操作都必须遵守。**

- 适用范围：`group4@10.123.0.39`（worker00039）及 `/home/group4/`、`/data/group4/` 下所有路径。
- 生效日期：2026-09-29
- 现场更新：2026-10-03；环境/研究来源见`reports/20261003-codex-workflow-refresh-e517-report.md`；存储更正见`reports/20261003-codex-data-access-79b2-report.md`、`logs/notice-20261003-sonic-move/notice.md`及journal第404条。容量/权限使用前重查。
- 局部修订：2026-10-03；以最初495行版本为底稿，保留章节编号、有效条款和事故证据。冲突条款在原位置改正；历史原文与逐项差异保留在本次报告，不再并列两套执行流程。
- 制定者：DASC7606C group4（12 人共享一个 Unix 账号）
- 你开始动手前的第一个动作：**读完本文件，并执行「开工三步」**。

---

## 0. 为什么必须有这份文件

12 个人共用 `group4` 这一个账号，Unix 层面**无法区分谁是谁**。任何代理写的命令，在 `syslog`、`history`、文件属主上都只显示 `group4`。因此：

- 一个代理误删/覆盖另一个代理的文件，**无法追责、无法恢复**；
- 两个代理同时改一个文件，后写的会静默吃掉先写的，没有任何报错；
- 一个代理写坏共享配置（`~/.bashrc`、`~/.ssh/`、`~/.gitconfig`），可能破坏登录或共享工具行为，影响全组12人。

所以这里的所有约定不是为了整洁，是为了**不让队友的工作消失**。

---

## 1. 工作区边界（第一红线）

代码、认领、台账、操作流水与报告统一放在：

```
/home/group4/group4_dasc7606c/
```

大权重、数据集、大缓存、编译中间物及大体积产物优先放在`/data/group4/<TASKID>/`自有目录，并在上述项目目录的card/报告中登记实际路径、来源、hash与引用关系。2026-10-03实测`/data/group4`属group4且可写；`/data`根目录仍属root且不可写。两块盘分别核权限、峰值空间与余量（§6），不把根目录权限推成整卷不可用；仍须先认领，不因同属group4就修改已有目录。

### 1.1 目录归属表（已存在的目录，用途固定）

| 目录 | 用途 | 谁可写 |
|---|---|---|
| `repos/` | clone 的源码仓库 | 领了"源码/依赖"任务的代理 |
| `weights/` | 既有模型权重/兼容入口；新大权重优先`/data/group4/<TASKID>/weights/` | 领了"权重下载"任务的代理；不自动迁移既有权重 |
| `render_test/` | MuJoCo 渲染可行性试验 | 领了"渲染测试"任务的代理 |
| `musa_probe/` `musa_rootfs/` `images/` | MUSA 工具链镜像层拆解 | 领了"MUSA 环境"任务的代理 |
| `envs/` | Python 虚拟环境，**按任务命名**；新大环境可选`/data/group4/<TASKID>/env/`并登记路径 | 只允许写自己的环境；不得覆盖既有环境 |
| `logs/` | 操作流水、下载日志、报错原文 | 按任务建子目录 `logs/<task-id>/` |
| `reports/` | 交付报告（md，见 §3） | 只允许写**自己命名**的文件，禁止改别人的 |
| `tools/` | 公用二进制（`uv` 等） | **只读**，不许改动、不许往里装别的东西 |

### 1.2 禁止触碰

```
/data 根目录及 /data/group4 以外目录：未获写授权；/data/group4 自有任务目录按§1允许写
/usr  /etc  /opt 系统路径（禁止本任务写入；只读sudo白名单不等于系统管理授权）
/home/group4/.bashrc  .profile  .gitconfig  .ssh/authorized_keys 及任何 home 根下的既有配置文件
/home/group3/  /home/mccdoctor/  /home/mccxadmin/  /home/tidb/   别人的家目录
/tmp  中不是你自己创建的文件
```

10-03 SSH审计报告记载管理员配置了特定只读sudo白名单；实际使用须核对授权命令与本任务范围，不可安装、改系统配置、杀进程或借Docker绕过权限。本轮未使用sudo、未重测完整白名单。

`.ssh/authorized_keys` 默认禁止修改；仅在用户明确授权添加公钥的独立任务中允许**追加**（`>>`），永远禁止重写、删除、改权限——一旦写坏，全组都登不进去。

### 1.3 `/tmp` 会被重启清空——重要成果不要放那里

生效配置是 `D /tmp 1777 root root -`（`/usr/lib/tmpfiles.d/tmp.conf`）：`D` = **early boot 时清空该目录内容**，末尾 `-` = 不按年龄周期清理。所以`/tmp`平时看着不会掉，**但本节点已实证重启清空**；`/var/tmp`的清理配置需单独核验，不能仅由`/tmp`配置推出同样行为。本节点 09-29 10:53 为开 IOMMU 重启过一次，当时 `/tmp` 里凌晨建的工作目录全部消失，已实证。

规则：

- `/tmp` 只放**可重生成的中间物**（临时下载、编译产物、单次运行的 scratch）。
- `steps.md`、报告与台账留在项目目录；大体积`qpos`/`npz`/`mp4`、数据集、权重等优先落在`/data/group4/<TASKID>/`，报告写实际路径与manifest。持久卷不等于已备份：Git/bundle不包含这些大资产，另记来源、hash、重建方法与实际副本位置（没有副本就明确未备份）。
- 确实需要大空间而必须用 `/tmp` 时：**在 `claims/<TASKID>/card.txt` 里显式写明"这些东西重启会没"+ 重建方法（源 URL 与命令）**，让人一眼能恢复。
- 历史快照：`/home`曾剩80G、`/`含`/tmp`曾有160G+，不是当前容量。10-03已开放`/data/group4`且SONIC三卷已迁入；大件优先用它，`/tmp`仍仅自有可重建中间物。迁移已有资产先确认属主/授权、下载进程与打开文件、容器Mounts及引用；先复制、校验清单，再切换路径/兼容链接并复测，源删除单独确认；不照抄公告历史回滚命令处理正在使用的链接。SONIC三卷仍未齐，不因迁入数据盘宣布下载完成。
- 容器 bind-mount `/tmp` 下的目录同样受此影响：**跑着作业时移走/删除宿主目录，容器里的挂载路径就失效**。动手前先看 `docker ps` 与 `docker inspect <容器名>` 的 `Mounts` 段（确认 Source 是否指向你要动的目录），再用 `ls -l /proc/<PID>/fd | grep /tmp` 看有没有进程正打开里面的文件。

---

## 2. 开工三步（每次任务开始都要做）

```bash
BASE=/home/group4/group4_dasc7606c
TOOL=codex                          # 填自身工具名；真人填human
LOCAL_USER=ReAgain0                 # 填发起方本机用户名
SESSION_ID="${SESSION_ID:-$(python3 -c 'import uuid; print(uuid.uuid4())')}"
OWNER="$TOOL($LOCAL_USER<$SESSION_ID>)" # 同一会话保留SESSION_ID，格式见§4.2
TASKID="$(date +%Y%m%d-%H%M%S)-$TOOL-$(python3 -c 'import secrets; print(secrets.token_hex(4))')"
SCOPE='填写任务目的、允许写的路径和预期资源'
# ① 生成全局唯一task-id；② 原子认领，失败立即停止
mkdir -p "$BASE/claims"
mkdir "$BASE/claims/$TASKID" || { echo 'CLAIM_FAIL'; exit 2; }
mkdir "$BASE/work/$TASKID" "$BASE/logs/$TASKID" || exit 2
printf 'task=%s\nowner=%s\nsession_id=%s\nstarted=%s\nscope=%s\n' \
  "$TASKID" "$OWNER" "$SESSION_ID" "$(date -Iseconds)" "$SCOPE" > "$BASE/claims/$TASKID/card.txt" || exit 2
# 建立自有流水并记录读过的规则；规则变化先读差异
printf '# %s 操作流水\n' "$TASKID" > "$BASE/logs/$TASKID/steps.md" || exit 2
sha256sum "$BASE/AGENTS.md" > "$BASE/claims/$TASKID/rules_seen" || exit 2
# ③ 登记到总账，唯一写者内部持锁（见§4.2）
bash "$BASE/work/journal/tools2/journal_append.sh" "$TASKID" start - "$SCOPE" \
  --field "owner=$OWNER" --field "session_id=$SESSION_ID" || exit 2
```

`claims/` 下每个目录代表"有人在干这件事"。收工统一按§10先写并校验事实源事件，再生成`done.txt`；blocked不生成新完成标记。**不要删除claim目录**，保留记录。

---

## 3. 强制留痕（本规约的核心要求）

**一切操作都要落到 md 文件里**：操作步骤、执行流程、结果、报告。四样缺一不可。没留痕的操作等于没做过，且下次没人敢碰。

### 3.1 你要产出两个文件

| 文件 | 路径 | 内容 |
|---|---|---|
| **操作流水** | `logs/<TASKID>/steps.md` | **边做边写**，每个动作一条，含失败 |
| **结果报告** | `reports/<TASKID>-report.md` | 做完后写，结论 + 证据 |

> 除这两个文件外，**账本事件也算留痕**：开工记 `start`、完成记 `done`，未完成记 `blocked`（§10）（唯一入口 `work/journal/tools2/journal_append.sh`，用法见 §4.2 与 §10；脚本会自检锚点条数，不等就 exit 6）。`INDEX.md` 只是可重建视图，**别把手写 `>>` 往它追加当成留痕**。

### 3.2 `steps.md` 格式（每条操作）

```markdown
## [03] 2026-09-29 02:41:13  下载 uv 二进制
- 目的：节点无 pip，需要 uv 建 venv
- 命令：
  # 仅为流水格式示例；实际下载版本由任务确定，并先创建自有目录
  curl -sL -o "$BASE/work/$TASKID/uv.tgz" https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz
- 结果：成功
- 证据：http=200 size=19831732 字节；`uv --version` → uv 0.12.19
- 影响范围：仅 work/<TASKID>/uv.tgz 与 work/<TASKID>/tools/uv（示例；禁止覆盖共享tools/uv）
- 失败/重试：第 1 次 curl 被 40s 超时截断（7.9MB），改用 --max-time 120 后成功
```

要求：
- **失败也要写**，并把原始报错粘进去（截断到关键几行）。只记成功等于制造假象。
- **证据必须是实测数字**：字节数、版本号、耗时、退出码、`http_code/size_download`。
- 不许写"已确认""应该没问题"这类无数字断言。
- 没做成的事明确写"**未验证**"，不要靠推断填空。

### 3.3 `reports/<TASKID>-report.md` 结构（固定六段）

```markdown
# <任务名> 报告
- 执行方：<工具名> / task-id / 起止时间
## 一、结论        （3 行内说完，明确给出"能 / 不能 / 有条件能"）
## 二、操作步骤    （要点列表，指向 steps.md）
## 三、实测证据    （表格或代码块，数字、命令输出原文）
## 四、失败项与原因（每条附完整报错原文）
## 五、下一步建议  （具体到命令，不要写"进一步优化"这类空话）
## 六、复现方法    （能直接粘贴执行的命令块）
```

### 3.4 双向归档（服务器 + 本地各一份）

报告必须在**两处都留档**：服务器 `group4_dasc7606c/reports/`，以及发起方的本地工作目录 `server_reports/`。只留一份不算完成。

归档后核对两端SHA-256，保存服务器路径、本地路径与结果；拿不到本地副本时标`archive pending`。Git文本留档不包含权重、环境和全部仿真资产，大资产另记来源、hash和重建方法。

**Git收工留档（新增检查项，依据本次遗漏审计与既有台账仓工作流）**：仅提交授权范围内自己的修改和必要事实源快照，保留全部原作者事件。先保存HEAD、暂存路径清单、索引备份及重叠路径旧blob；使用本会话独立author/committer，不改共享.gitconfig。按显式路径`git add -f -- <路径...>`，再`git commit --only -- <相同路径...>`，验证提交文件列表、hash与其他路径暂存blob一致。禁止`git add -A`、全局reset或提交整个共享暂存区；嵌套Git仓单独提交。涉及同路径他人修改必须先核对归属/差异，无法安全分离则标`git pending`，不能擅自代提交。登记提交结论形成的新账本尾部可下一次增量留档，但须注明快照截止位置；不擅自push或恢复自动提交cron。收工清单在§10引用本节。


---

## 4. 防止两个代理写同一个文件

### 4.1 命名即隔离

**禁止在共享目录直接**使用这些通用文件名（必撞）；在已带TASKID的自有子目录内允许`steps.md`、`output.log`等短名（与§3一致）：`report.md`、`README.md`、`result.md`、`notes.md`、`output.log`、`summary.md`、`log.txt`。

**必须**带上 task 标识：`logs/20260929-0241-qoder-a3f1-weights/steps.md`、`reports/20260929-0241-qoder-a3f1-weights-report.md`。

### 4.2 共享账本必须持锁追加

任务账本与视图（统一入口，不另建账本）：

```
claims/journal.log   ← 只追加的任务事实源，配套journal.anchor
claims/INDEX.md      ← 可重建的当前任务视图，禁止手写追加
INDEX.md            ← 根目录历史兼容记录，保留不删；不作当前状态入口
```

`flock`在节点上可用（`/usr/bin/flock`）；以下仅解释接口，**不是第二次开工步骤**。已执行§2的任务不再start；继续先查同TASKID最新事件，未结束用note记恢复，已done则新建任务。接口示例：

```bash
TS="$(date '+%F %T')"     # 在 flock 外算好
bash "$BASE/work/journal/tools2/journal_append.sh"      "$TASKID" start "<gpu>" "$TS <一句话任务>"
```

- 账本事实源是 `claims/journal.log`（JSONL + sha256 链 + 锚点），**只追加**；`claims/INDEX.md` 是它的可重建视图，不要手写 `>>` 进视图。
- 账本串行化由 `journal_append.sh` 内部的 `claims/journal.lock` 负责；拿不到锁就让它超时报错，**不要绕过脚本裸写**。
- 认领卡号必须与 `MUSA_VISIBLE_DEVICES` / `MUJOCO_EGL_DEVICE_ID`（倒序表）逐一核对后写进 `steps.md`。
- **`card.txt`的`owner=`必须区分工具、本机用户和会话**，格式`<工具>(<用户名><会话标识>)`，如`codex(ReAgain0<会话UUID>)`、`qoder(reagain0<会话UUID>)`；单尖括号，不用`<<>>`。工具无关形状正则`^[A-Za-z0-9._-]+\([A-Za-z0-9._-]+<[^<>]+>\)$`只检查格式，不证明唯一性。新任务另存完整`session_id`，同会话保持一致；短号/目录末段只作显示，旧卡不批量改写。**跨会话代补、催收或转告之前先读`claims/<TASKID>/card.txt`认归属**——09-29夜到09-30凌晨四次误判（`ardyseed`、`vljudge`、`nl2constr`、`session-watch`）均与仅写`owner=qoder`有关；后续还出现短号碰撞，见`ISS-IDENTITY-SID8-COLLISION`。Git身份同样含会话标识（§3.4），不得共用author。

### 4.3 目录分工，不重叠写

同一时刻，一个目录只有一个属主任务。要复用别人产出时：**只读**，需要改动就整份复制到自己工作区再改。

```bash
cp -r "$BASE/repos/kimodo" "$BASE/work/$TASKID/kimodo"   # 只读源，先确认自有目标不存在
# 不要直接在 repos/kimodo 里改（除非这个目录的属主就是你）
```

### 4.4 独占资源用 claim 目录

任务内声明（仅留痕，不是跨任务互斥）：

```bash
mkdir -p "$BASE/claims/$TASKID/resource"
mkdir "$BASE/claims/$TASKID/resource/weights-kimodo" || exit 2
```

不同TASKID的上述目录都能mkdir成功，所以不能据此声称“别人被挡”。写同一共享资源须与属主确认授权，并由参与方使用**同一路径锁**完成检查和修改，例如`flock -w 30 "$BASE/claims/weights-kimodo.lock" <已授权写入命令>`；拿不到锁或属主不明就停止。先检查其他未收口声明，不能只检查自己的resource目录；GPU分配流程统一见§6。

---

### 4.5 `crontab` 是全账号唯一的文件（装定时任务 = 整体替换）

- `group4` 是 12 人共享账号，**整个账号只有一个 crontab**，所有会话的定时作业都挤在同一份里。`crontab <file>` 是**整体覆盖**：别人那几行会被静默删掉。
- 这类删除**不留证据**：`/var/spool/cron/crontabs/group4` 是 `0600 root`（读不到历史），`/var/log/syslog` 属 `syslog:adm`（我们读不到），目录 `mtime` 只能看出"最后一次写是几点"，看不出删了谁。所以**误删无法归责，只能预防**。
- 装cron统一四步：① 读取并备份**当前完整表**，读取失败先停止；② 使用下述`cron_install_safe.sh --dry`预览并检查自有标记块，确认非自有行及重复次数保持；③ 经授权后由同一安全入口安装；④ 回读核验并保留前后hash。不得手搓覆盖，也不得把旧备份整体盲恢复吃掉后来的行；回滚需在锁内确认无并发漂移后恢复，漂移则按标记合并。
- **`crontab -l` 返回 0 行不等于"没有别人的任务"**——可能是并发覆盖、也可能读取失败。装之前必须把整份内容打印出来看一眼。
- **有现成工具就用工具**：`bash $BASE/work/journal/tools2/cron_install_safe.sh --block <自有块文件> --marker <会话标记> [--dry]`（合并内核直接 source 本节末 advice 的 `lib_cronmerge.sh`，不重复实现）。它比手搓四步多三件事：① 自有块已逐行在位时**直接判不动表**（保持别人看到的行序，不做无意义的挪位）；② 需要写时走 anchored 合并，并做**多重集硬断言**——快照里任何一条非空行按出现次数少掉就 **exit 6 拒写**（实测阳性对照：把合并库换成整表 `sort -u` 吃掉一条重复行 → 拒写、表逐字节不变、台账记 `refused_lost_lines`）；③ 写回后再回读复核，不合格**自动回滚**并记 `rolled_back`。全程用 `flock` 包住读改写（`$BASE/cron.d/crontab.lock`），台账在 `$BASE/logs/cron-table/ledger.tsv`。03:31 对真表实跑：判定"自有块已逐行在位，**不动表**"，真表 md5 `9efd90b5…` 前后一致。
  - 已知边界（别当保险箱）：自有块只做**形状**校验（注释行或以时间字段开头），不审查命令语义；`crontab` 本身不设防，**裸敲 `crontab` 依然是第一禁忌**；若现表含逐字重复的他人作业行，合并会按多重集处理，重复行不会被吞（这条已被阳性对照测出）。 安装前确认合并库实际存在，缺失则停止，不能落入退化合并。入口rc=0表示已满足/未写，rc=3表示已写入且核验成功，其余按脚本错误码处理；不能一概把非零当失败。本修订不安装或修改cron。
- 每条自有作业行**上方写标记注释**（例 `# QODER-JOURNAL-DAILY main-63af4ba4 …`、`# QODER-RESTORE-D9 …`），下一个 agent 才知道这行归谁、能不能删；装之前先 `crontab -l | grep -q <标记>` 做幂等，命中就别装第二遍。
- **事故定案（09-30 02:05:17.817 清空 → 02:37:11 复原。本条为 02:50 更正，替换原"某会话装自有 cron 时读到 0 行、写完后双双消失"那句——那句把嫌疑指向了安装动作本身，证据不足）**：
  **真凶是"无参数 `crontab`"**。`man 1 crontab` 写明 `default operation is replace, per 1003.2`，无操作数时**从 stdin 读新表整体替换**；非交互 SSH 里 stdin 立刻 EOF ⇒ **空表被当成新表装回，且没有任何 stderr 输出（静默成功）**。
  时间线（一手取证来自 `20260930-0206-qoder-cronsafe` 会话的自曝）：02:03:58 表内 2 行 / 726 B（md5 `7744db64…`）→ 02:05:01 autocommit 仍准点提交（此时表完好）→ **02:05:17.817 spool 最后一次写入** → 02:06:06 起 `crontab -l` = **0 字节**（md5 `d41d8cd9…` 即空串的 md5），02:07:04 / 02:11 / 02:33 三次复测仍 0 字节 → 02:28 另一会话空读后装入自己那行（**它接手的是空表，不是它清的**）→ 02:36:18 用"有 11 个未提交改动却不产生 02:35 提交"的活体判据实测确认停摆约 31 分钟 → 02:37:11 逐字复原（现表 6 行 / 1278 B）。详见 `reports/crontab-safety-advice-20260930-0206-qoder-cronsafe.md` §0。
- **由此第一条禁忌：永远不要裸敲 `crontab`**（既不带 `-l/-e/-r/-u`，也不带文件参数）。它**不是**"查看用法"，它是**写操作**，并且**静默成功**。开发期挂只读 shim（advice §2.4 有实测可用版本），装表前后各留一次 `crontab -l | md5sum` 台账（advice §2.6），合并优先用按标记合并的 `cronmerge.sh`（advice §2.2，在 `work/20260930-0206-qoder-cronsafe/scripts/`）而不是自己手搓覆盖。
- **盲装旧快照同样危险**：事故前快照 `work/20260930-0206-qoder-cronsafe/ct.pre` 里 `grep -c journal.daily.lock` = **0**，直接 `crontab ct.pre` 就会吃掉别人新装的行；正确顺序是先 `crontab -l > 现场快照` 看非 0 就走 merge（advice §五）。  <!-- 锚点 CRONTAB-SAFE-20260930 -->
**2026-10-03 05:35现场**：crontab有日检、identity保活、disk-guard三条作业；旧ledger autocommit注释仍在，但未见对应Git命令。SSH报告§11曾写“显式四事实源自动提交已补回”，所指`logs/20261003-ssh-autocommit-restore/report.md`与`logs/session-watch/ledger-autocommit.log`本轮stat也未见。记录不一致到`ISS-AUTOCOMMIT-ADD-A-BLAME`，不据注释宣称自动留档有效、不改他人cron；当前仍按§3.4手工显式Git。

### 4.6 待解决问题登记簿（开放问题的事实源）　【锚点 OPEN-ISSUE-REG-20260930】

§3 的留痕只回答"我做了什么"，没有地方放"还有什么事没人做"。这类内容历史上散在几十份报告的"§五 下一步建议"里，**接手的人不会去翻**，于是问题烂在文件中。现以登记簿为唯一入口：

| 物件 | 路径 | 性质 |
|---|---|---|
| 事实源 | `claims/issues.jsonl` | **只追加**；每行 `prev = sha256(上一行原始字节，含行尾换行)`，首行 prev 为 64 个 `0` |
| 锚点 | `claims/issues.anchor` | 每行 `(seq, 全量 sha256, ts, issue)`，用于检出"末尾被删/整体替换"（纯链检不出这种） |
| 人读视图 | `reports/open-issues.md` | 由事实源**重建**，旧版自动备份为 `open-issues.md.bak.<时间戳>`；**禁止手工编辑** |
| 唯一写者 | `work/20260930-0310-qoder-issuereg/issue_append.sh` | 内部持 `claims/issues.lock`（**独立于 `journal.lock`，不得嵌套**）；追加后回读校验 JSON 合法与行数增长，失败即报错退出 |
| 校验 / 重建 | 同目录 `issue_verify.sh`、`issue_view.sh` | verify 的 exit=0 表示 链/JSON/空行/seq/锚点 全部完整；两者都支持 `ISSUES_BASE=<沙箱目录>` 离线试跑 |

用法（`event = open | note | close | handoff`；`state = OPEN | BLOCKED | WATCH | CLOSED`）：

```bash
B=/home/group4/group4_dasc7606c; IA="bash $B/work/20260930-0310-qoder-issuereg/issue_append.sh"
$IA --ts "$(date +%Y-%m-%dT%H:%M:%S%:z)" <ISS-ID> open OPEN "<一句话标题>" "<正文>" \
    --field owner_scope="该谁做（写任务 id 或角色，别只写 qoder）" --field severity=高 --field est_cost="20min" \
    --field evidence="reports/xxx.md §三; work/xxx/out/yyy.json"
$IA --ts "$(date +%Y-%m-%dT%H:%M:%S%:z)" <ISS-ID> handoff OPEN "<原标题>" "由 <我的TASKID> 认领，计划：<一句话>" --field owner_task=<我的TASKID>
$IA <ISS-ID> close CLOSED "<原标题>" "判据：<实测数字>；证据：<路径>" --field owner_task=<我的TASKID>
bash $B/work/20260930-0310-qoder-issuereg/issue_view.sh && bash $B/work/20260930-0310-qoder-issuereg/issue_verify.sh
```

四条规矩：

1. **正文必须写清四件事**：现象、已有实测证据的路径、接手人要做的**具体动作**（可直接粘贴的命令）、判据与预计成本。只写"待优化"的条目视为无效登记。
2. **§11 接手任务时先读视图**（`reports/open-issues.md`）；认领用 `handoff` 事件，不要用"编辑视图"或"占文件名"的方式声明所有权。
3. **结案必须带数字**：`close` 的正文里要有可复核的实测值或路径；解决不了就如实写"未验证 / 做不了的原因"（沿用 §3.2 的"不许写无数字断言"）。
4. 链约定与 `claims/journal.log` **不同**（那边是 `prev = sha256(上一行去掉行尾换行)`），两套账本的校验脚本不可互换，混用会误报断链。写坏的行**不要删**，用 `note` 事件更正，历史留在链上可查。

历史待办合并流程：阅读原报告的“下一步/未解决” → 查询现有issue → 同一问题补`note`并保留源路径/证据，别名归入已有ID → 确属新问题才`open` → 重建并校验视图。旧backlog、交接清单、研究建议保留作证据，不再维护另一套当前状态；可选方案用WATCH并注明待谁决策，不把所有研究想法变成强制任务。已完成的合并对照见`reports/20261003-codex-git-issues-4f26-mapping.json`，登记不等于解决。

链/锚点校验只能证明记录内部完整性，不能证明结论真实；数据和锚点一起截断还需Git历史或独立备份识别。两套验证器不可互换。

---

## 5. 破坏性操作

- 本目录下**禁止 `rm -rf`**、`find -delete`、`chmod -R`、`chown -R`。
- 清理只针对自己创建的具体文件，且先 `ls` 确认再 `rm`（不带 `-r`）。
- 需要清空自己工作区：先 `mv` 到 `logs/<TASKID>/trash/`，留下记录，不要直接删。
- 任何 `>` 重定向写入前，先 `ls` 目标是否已存在、属主是谁。

---

## 5A. 远端写入与测试自证（两条纪律；2026-09-30 本节点踩坑实录）【锚点 DISCIPLINE-REMOTE-WRITE-20260930】

> **等级说明**：真实写入、真实测试、隔离与真实完成属于§3/§10强制要求；以下传输/自检模板为建议实现，可采用具有同等隔离与证据的其他方法。保留原事故与建议，不限定只能用某个模板。

### 5A.1 向节点写多行内容：禁止用未加引号的 heredoc 承载

规则：内容里只要可能含**反引号、`$`、`\`**（命令行示例、代码片段、Markdown 内联代码都算），优先采用"**本地成文 → scp 上传 → 远端只读该文件**"；其他方式须避免shell展开并核对内容hash，不要用 `cat > f <<BLOCK … BLOCK`。heredoc 定界符**不加引号时 shell 会对块内做展开**：反引号＝命令替换、`$x`＝变量替换；要写内联 heredoc 也必须用 `<<'BLOCK'`（带引号）。

正确模板：

```bash
# 本机Bash示例：先以编辑工具生成LF文件；TASKID填本次已登记的任务号
: "${TASKID:?先填写自己的TASKID}"
scp local_block.md "S4000:/home/group4/group4_dasc7606c/work/$TASKID/blk.md"
# Windows PowerShell可使用scp同样的完整目标路径，本机hash用Get-FileHash
# 下列在节点执行；两端SHA-256相同后再使用，不能只核文件大小
BASE=/home/group4/group4_dasc7606c
: "${TASKID:?先填写自己的TASKID}"
wc -c "$BASE/work/$TASKID/blk.md"
sha256sum "$BASE/work/$TASKID/blk.md"
tr -cd '\140' < "$BASE/work/$TASKID/blk.md" | wc -c # 数反引号，勿写字面反引号
# 本机先转LF；上传有CR时停止并修正自己的副本，不直接修改共享文件
[ -s "$BASE/work/$TASKID/blk.md" ] || { echo 'ERR: 上传文件为空'; exit 8; }
```

反例与代价（实测）：写 AGENTS.md §7A 时用了未加引号的 heredoc，块内 **122 个反引号**被远端 shell 当命令执行，文件只多出 **29 行残骸**（正确应为 39 行），而当时三项常规检查全都"通过"：命令返回码 0、文件行数在增加、`grep '^## 7A'` 命中。⇒ **这三项都是假成功信号**，必须补三项独立自证：独有句各命中 1、代码围栏行数为偶数、残骸特征计数为 0。同类二次翻车：把字面反引号放进 `ssh '…'` 里的 `grep -c` 模式，导致整条命令语法失败、后续检查全部没执行。

**写自校验脚本时的两个必要约束**（本条来自 09-30 另一次返工：我加的"排除自身"检查反而把文件装坏了）：

- **边界锚不能出现在自检代码自己身上**。用 `s.find("## 6.")` 定位下一节起始，会被示例代码里那句 `s.find("## 6.")` 先匹配到，边界算进本节点内部 ⇒ "排除自身"变成"排除到半句中"，比对必然假失败/假通过。要写**带换行且含标题正文**的锚，如 `s.find("\n## 6. GPU")`，并确保示例代码里不出现同样的完整字串。
- **每一步都检查返回值，失败立即停止，再按§5A.3核对现行hash后回滚**。`set -uo pipefail`不会因某步非零自动停下；Python的`SystemExit`只结束Python。多步共享修改须显式处理每步失败并保存报错，不能校验FAIL后继续安装，也不能盲cp旧备份覆盖后来修改。原事故是“校验打印FAIL、脚本照样把文件装回去”，教训保留。

### 5A.2 宣布"测试 PASS"之前，必须先证明测试走到了目标分支

规则：自造回归/沙箱测试里，**断言之前要有前置条件自检**——目标目录与文件确实存在、字节数非零、被修改的那条分支确实执行过（最省事的做法是让脚本自己打印一行分支特征）。自检不成立时**记 `blocked` 并在 steps.md 写报错原文**，不得记 `done`/`PASS`。

反例与代价（实测）：修 `close_ledger.sh` 的沙箱回归里只 `mkdir -p $SB/claims`、漏建 `claims/task-keep`，于是 `printf > …/done.txt` 落空，"已存在则保留原时刻"这条分支**根本没被执行**，我却把"两例 PASS"写进了哈希链账本（journal `#171`）与 INDEX。复测（先建目录、直接调真实安装的脚本）才拿到真证据：`done.txt` md5 `6cd6e335…` 前后未变、mtime 未变、journal 收到 `done_txt_ts=2026-09-29 23:19:24`。错误断言只能靠追加 `note` 事件更正（`#172`，字段 `corrects=171`），**历史行不抹**——账本只追加，改了必断链。

与既有条款的关系：§3 要求"失败也要写、证据必须是实测数字"；§10 收工流程里 done 事件应当对应**真实完成**。本节补的是它们的盲区：**"写对了文件"与"测对了分支"都需要独立自证，不能拿命令返回码当结论**。
### 5A.3 共享规约变更与沙箱（合并既有建议的流程要求）

修改AGENTS或共享工具：确认用户授权范围 → 保存现行hash与基线备份 → 在自有副本编辑、实验并保存最小diff → 写前再次核对hash → 原子替换 → 独立复读验证 → `RULES-CHANGELOG.md`和journal追加note。AGENTS发布使用`claims/rules.lock`短锁；不要在journal/gpu/issues临界区改规约。回滚前检查漂移：未变可恢复本次备份；后来有人修改则逆转自己的hunk或三方合并，不能旧快照整体覆盖。来源：`reports/inbox-design-v2-and-rules-change-protocol-20260930.md`；本文不安装信箱或全局哨兵。

共享修改/占资源前比对本任务`rules_seen`与现行AGENTS hash；变化时先读差异并更新自己的记录。仅是调用者自检，未安装全局规则哨兵，不能强制旧会话更新。

沙箱测试必须显式选择真实目标：子shell内设置`JOURNAL_BASE=GPU_BASE=ISSUES_BASE=<本任务sandbox>`（仅为实际用到的工具），清理继承的`JOURNAL/ANCHOR`，核对解析后的账本、锚点、视图与符号链接均在自有沙箱。不能只凭任务名含sandbox或只设GPU_BASE判断隔离。脚本及种子复制到自有目录；不直接运行他人的固定路径自测，以免覆盖其证据。保存目标路径及生产文件前后hash；正常、失败分支都需实际命中再声明PASS。

## 5B. 派子代理上机：任务书第一条必须是连通性探针【锚点 SUBAGENT-SSH-PROBE-20260930】

> **是否委派为可选**；需要远端证据时，先验证连通性、不得把连接失败当文件缺失是强制真实性要求。下列SSH探针为建议实现，可用等价可复核方法替代，不要求所有任务派子代理。

规则：**需要上机取证的委派任务，第一步必须验证连通性（可用下列探针或等价方法）**，并要求把「命令原文 + 完整输出 + 退出码」三段贴回它自己的 `steps.md` 第 [01] 条；退出码非零 ⇒ 立即中止并上报"我这侧连不上节点"，**禁止**继续推断远端有什么、没什么。

可直接粘进任务书的首段：

```
第 0 步（必须先做，失败就停）：在 Bash 里执行
    timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=10 S4000 'hostname; date "+%F %T"'
把命令原文、stdout/stderr 全文、退出码三段原样贴进 steps.md 第 [01] 条。
退出码非 0 或输出里没有 worker00039 ⇒ 中止本任务，结论段第一句只写"我这侧连不上节点，未取得任何远端事实"，
不得把它解释成"远端文件缺失 / 目录为空 / 成果被清理"——那类断言必须逐条 stat 取证才允许出现。
```

反例与代价（实测）：子代理 `fb32-locate` 连节点都没连上（ssh 别名不可解析 + 一次尝试被权限系统拦下后它没重试），却在结论里断言"远端工作区只剩空骨架、5 个脚本 MISSING"，并列出不存在的路径。主会话 `stat` 逐个证伪：`AGENTS.md` 28690 B、`INDEX.md` 156 行 / 36177 B、`claims/journal.log` 91312 B、那 5 个文件**全部 EXISTS**，而它自己的 `claims/<TASKID>/` 目录根本没建、账本里 0 条事件。⇒ 它没编数字、也没越界，但**一个答案都没拿到**，白烧掉一整轮额度，还差点把"远端空了"这个假事实带进报告。

阳性对照（同夜实测）：子代理**是能上机的**——探针在 03:38:41 返回 `worker00039` + 节点时间，走 `IdentitiesOnly` 那条路径可用；私钥在 Git-Bash 里显示 `644` 是 Windows 假象，真实权限由 NTFS ACL 决定。⇒ "连不上"要分清三种因：别名不可解析 / key 与 ACL / 节点真不可达；**没有一种等于"远端文件不存在"**。

父会话一侧的对偶要求：收到子代理报告后，凡是"远端不存在 X""X 已被清掉"这类**否定断言**，必须自己 `stat`/`ls -l` 复核一次才允许进报告或账本（与 §5A.2 同源：断言要走到目标分支才算验过）。

判据（本轮怎么算做到位了）：该子代理的 `steps.md` 第 [01] 条含三段探针输出；其结论段若承认连不上，则不得同时出现任何远端文件状态断言。补充一条经验：**需要实机执行的活优先主会话自己做**，委派优先用于纯本地分析或纯检索；确需远端取证按本节验证连通性——探针要求是兜底，不是把远程实机活派出去的理由。开放问题登记簿里对应条目：`ISS-SUBAGENT-NODEACCESS`。


## 6. GPU 与共享资源

- **只有 4、5、6、7 号卡属于本组（group4）。0–3 号归 group3（邻组）专用，任何时候不得占用。**
- 环境变量只暴露**本任务获准的4–7号卡子集**，例如单卡`MUSA_VISIBLE_DEVICES=6`；禁止`all`。官方镜像的默认全8卡必须覆盖；容器另核对`MTHREADS_VISIBLE_DEVICES`，最终以实际可见设备为准。
- 占卡前后各跑一次`mthreads-gmi`并记入`steps.md`；只检查目标卡，不因其他本组卡忙而阻止使用未被认领的空闲目标卡。

> **统一操作块（GPU-USAGE-MERGED-20260930；历史实证仍见`reports/gpu-usage-merged-20260930.md`）**：原“Processes有PID就停”“瞬时取锁等于空闲”“服务先启动再登记”均已撤回；以下是合并后的执行顺序。
> - 判卡看目标卡`Used`数值、已有resource声明和未收口claim；Processes中同一PID在8卡各有`<1MiB`枚举条目本身不证明负载，实测两例。目标卡不能证明空闲，或已有有效认领时停止并记证据，不擅自宣告他人claim过期。
> - **短锁内检查并预留 → 释放分配锁 → 启动 → 登记PID/容器ID和claim → 退出并核验 → 释放自己的预留**。检查与预留须由协作写者使用同一个`claims/gpu.lock`完成，预留在锁外保持可见；不能只`flock ... sleep 0`后抢占，也不能先起服务后认领。未能确认共享声明/旧任务状态时先停。
> - 常驻服务不要把作业运行包进全局分配锁。锁能取不代表卡空闲，锁被挡也不代表全组卡忙：历史一次服务持锁4小时，其余卡`Used 0MiB`。`flock`带有限`-w`，失败明确记录；`kill`父进程不一定放锁，因为子进程可继承open file description，定位持锁者看`/proc/locks`第5列PID。
> - 既有工具`work/p0lock/{gpu_free,gpu_lock,close_ledger,lock_report}.sh`需按上述语义检查，不能把旧包装器长持锁或空闲快照当已实现原子预留。上一轮自有`gpu_reservation.py`仅是已CPU沙箱测试的辅助实现，不要求全组切换，未验证旧会话协作或真实GPU启动。
> - 本组4–7同属一个MPB组，TP≤4不需跨组；认领物理卡号与`MUSA_VISIBLE_DEVICES`/容器可见卡/`MUJOCO_EGL_DEVICE_ID`倒序表逐一核对，记录实测映射，不能猜逻辑序号。
> - 收工账本与标记统一按§10：事件成功追加并校验后才创建完成标记，再刷新视图；并非跨文件原子事务。异常写note或blocked，不为清零而杀别人的进程；资源生命周期按下述普通实验/常驻服务分别处理。 普通实验须退出并释放；明确授权的常驻服务将部署任务与资源生命周期分开：部署可在验收并明确运行属主/停止范围后收口，运行资源claim持续有效。交接须承接人确认，无确认不冒充交接；不得为写done释放仍运行的预留，资源任务不因部署done自动结束。
> - 按卡分锁仍押后至两周数据；判据仍为`lock_report.sh`“被挡时存在空闲卡占比≥50%且周均可省≥2h”，本版不部署分锁。
- 磁盘红线：动手前`df -h /home /data /tmp`并核实际落盘目录可写；逐卷估算下载、展开、缓存与峰值临时空间，预算后各实际写入卷保留至少30GiB。某卷不足时停止该卷新增大下载/安装/编译，不把/home低余量误判为/data也禁止；不删除他人资产腾空间。10-03本次快照/home可用约16.8GiB、/data约11.73TiB、根卷含/tmp约148.9GiB；数值仅快照，使用前重查。有界小文本日志/证据可留home。HF/uv/解压临时目录须显式指到自有数据目录，防默认缓存回写home、同份数据占两遍；venv目标卷也纳入预算。
- 05:35宿主nproc=128；free -h总内存1.0Ti、available=971Gi。历史1007G是旧显示口径，不代表每个容器额度；编译仍-j32以内，CPU实验限制线程/样本/预算。

- **容器 bind-mount 写回宿主会以 root 落盘，group4 之后删不掉。** `docker run -v $BASE/xxx:/v` 里容器进程默认 uid 0，产物在宿主上属主是 `root:root`，我们既不能改也不能删，只能请机房 root 清理。实测代价：一次探针运行在 `logs/` 下留下 **166 个 root 属主文件**（含 `out/pylibs/` 整片），该历史快照不能由group4自行清理；当前是否仍166个须逐路径核验，`ISS-MT-ROOTOWNED-166`仍BLOCKED，本轮未重数/处理。规矩：
  - 跑容器一律加 `--user $(id -u):$(id -g)`；或
  - 把容器输出目录放到 `/tmp/<自己的任务名>/` 下（重启即清、不污染归档区），成果再由 group4 自己 `cp` 进 `$BASE`；
  - 若已产生 root 属主文件，**不要试图绕过权限**，在 `claims/<TASKID>/card.txt` 里登记路径与请求清理，攒进给机房的清单。

---

## 7. 网络与源（历史实测，首次使用或异常时复核）

以下可用性、Python版本与源速度为2026-09-29至09-30相应环境的实测记录，不保证当前不变。优先复用记录，首次使用、错误或环境漂移时做最小只读探针并记录日期，不重复大下载。

可用：`github.com` `codeload.github.com` `raw.githubusercontent.com` `pypi.tuna.tsinghua.edu.cn` `gitee.com` `hf-mirror.com` `www.modelscope.cn` `developer.mthreads.com` `registry.mthreads.com`（**Harbor 允许匿名拉取**，`/v2/` 返回 401 只是标准挑战，按 `Www-Authenticate` 换 token 即可）。

不可用：`download.mthreads.com` `oss.mthreads.com` `sh-moss.mthreads.com` `sh-repo.mthreads.com` `huggingface.co` `registry-1.docker.io` `files.pythonhosted.org`。

05:35只读复核：宿主/usr/bin/python3为3.10.12，pip/ensurepip均不存在，共享tools/uv为0.12.19。新任务须记录实际解释器路径/版本/pip，任务venv/容器与vllm shebang分别核对，不能把宿主快照套到容器。优先只读复用已验证环境；新环境按下例用共享uv，不覆盖升级它。网络列表与测速仍是旧环境记录，本轮未重测网络源。

```bash
: "${TASKID:?使用已登记任务号}" "${PACKAGE:?填写包名}"
DATA_ROOT=/data/group4
D="$DATA_ROOT/$TASKID"
# 先按§6预算/data与/home；只建自己的任务目录，不覆盖已有环境
[ -d "$DATA_ROOT" ] && [ -w "$DATA_ROOT" ] || exit 2
mkdir "$D" || { echo "DATA_DIR_EXISTS_OR_FAIL: 先核自己的claim/目录归属再恢复"; exit 2; }
mkdir "$D/tmp" || exit 2
export UV_CACHE_DIR="$D/uv-cache" HF_HOME="$D/hf-cache"
export HF_HUB_CACHE="$HF_HOME/hub" TMPDIR="$D/tmp"
ENV_DIR="$D/env"                   # 大环境避免再占/home；路径写入card/报告
"$BASE/tools/uv" venv --python 3.10 "$ENV_DIR"
VIRTUAL_ENV="$ENV_DIR" "$BASE/tools/uv" pip install \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple "$PACKAGE"
```

`tools/uv` 本身是共享只读文件，**不要覆盖或升级它**；需要别的版本就复制到你自己目录。

---

## 7A. 推理选型硬标准（vLLM-MUSA / torch_musa；2026-09-30 本节点实测）【锚点 INFER-STANDARD-20260930】

> 保留09-29/30相应build的实测与原数字，出处见7A.4；当前流程及后补状态以本轮更新为准。更换模型/镜像/版本需重核参数、后端和正确性，不将旧记录作跨版本硬标准。

### 7A.1 VLM 走 vLLM 服务化：必须锁视觉塔后端

历史build模板（先确认模型与CLI支持；MAX_MODEL_LEN不超过模型derived上限，BLIP历史为2048，不能一律4096）：

```bash
: "${MODEL:?填写模型}" "${MAX_MODEL_LEN:?先核derived上限}"
vllm serve "$MODEL" --trust-remote-code --enforce-eager --block-size 32 \
  --attention-backend FLASH_ATTN --max-model-len "$MAX_MODEL_LEN" --gpu-memory-utilization 0.6 \
  --mm-encoder-attn-backend TORCH_SDPA
```

- **上卡前先算** `head_dim = hidden_size / num_attention_heads`。MUSA 的 flash_attn **varlen 入口实测只支持 {64,128}**；`_MUSA_FLASH_ATTN.abi3.so` 里那句 `Only 64, 128, 256 are supported` **对 varlen 不成立**（256 实测被拒，别信字符串）。
- 病灶链条：vLLM 的 `supports_head_size` 只查 `%8==0 且 ≤256` ⇒ 放行 72/80/88 ⇒ 内核抛 `Unsupported head dimensions: d_qk=NN` ⇒ 被 `flash_attn/vllm_interface.py` 的 `except` 兜进 `torch.bmm(q, k.transpose(-2,-1))` + `softmax(dim=-1)` 回退，**该回退完全不读 cu_seqlens / seqused_k / block_table** ⇒ HTTP 200、格式正常、**视觉内容静默答错**。
- 已命中模型：Qwen2.5-VL 视觉塔 **80**（语言塔 128 ⇒ 文本对、图像错）、SmolVLM2 视觉 **72**、BLIP-2 视觉 **88** 且 OPT 语言塔 **80**（连纯文本都不可信）。
- **内核级判据**（比看答案快）：直打 `flash_attn_varlen_func`（bf16、两段打包 `cu_seqlens=[0,60,150]`）与 CPU fp64 精确参考对拍，`mean_abs_err` 呈双峰：64=0.169、128=0.165（无回退日志）↔ 72=0.732、80=0.731、88=0.738、256=0.760（全部回退）。误差从 ≈0.17 跳到 ≈0.73 即命中。
- `--mm-encoder-attn-backend TRITON_ATTN` **不能**用来救（引擎 `MUSA error: operation not permitted`）。`transformers + torch_musa`直跑路线不经过此vLLM回退路径，可作为对照；仍须核对CPU/精度与任务正反例，不能自动认定结果正确。
- 观测点：启动日志 `Using AttentionBackendEnum.<X> for MMEncoderAttention.`（`mm_encoder_attention.py:372`）与是否还有 `falling back to PyTorch implementation`。

### 7A.2 图模式（MUSAGraph）是降延迟，不是提吞吐

可用配置（**JSON 必须整体用单引号包住**，dotted 写法被 argparse 拒）：

```bash
--compilation-config='{"mode":0,"cudagraph_mode":"FULL","cudagraph_capture_sizes":[1,2,4,8,16],"cudagraph_num_of_warmups":1}' \
--max-num-seqs 16 --gpu-memory-utilization 0.6
```

| 场景 | eager | graph | Δ |
|---|---|---|---|
| 短 prompt 单流逐 token | 81.5 tok/s | **98.7 tok/s** | **+21%** |
| 512in/512out c=1 / c=8 / c=32（output tok/s） | 65.88 / 264.83 / 351.51 | 64.86 / 263.66 / 359.12 | −1.5% / −0.4% / **+2.2%** |
| mode=3 + FULL_AND_PIECEWISE（gm0.4） | — | 109.8 tok/s | +46% 但输出与 eager **md5 不同 ⇒ 判为不可用** |

- **是否实际启图**先看日志有没有`Graph capturing finished in N secs, took X GiB`。⚠️ `mode=0 + cudagraph_mode=FULL_AND_PIECEWISE` 会被 vLLM 自动降级为 `CUDAGraphMode.NONE`：服务照样起、速度≈eager，其实**没开图**（假阳性）。 图模式最终验收还需通过§7A.3正确性门及目标场景性能；出现capturing日志不能单独判PASS。
- 默认 51+35=86 个捕获尺寸需要 **25.31 GiB 图私有池**，gm0.8/0.6 直接 `torch.OutOfMemoryError … allocated in private pools (e.g., MUSA Graphs)`。⇒ 7B 卡在 capture 的病因是**显存预算**，不是驱动不支持（早先"graph 在 S4000 不可用"的结论已被本节点实测推翻）。
- `TRITON_ATTN` 作主后端在本 build/S4000 报 `Triton Error [MUSA]: invalid argument`（0.6B/7B 都复现）。

### 7A.3 通用参数、正确性门与测速判据

- **`--block-size 32` 必给**：flash_attn 源码原话 `S4000 only supports FA with page_size == 32!`。漏了它**连纯文本**都会退化成 ` of of of` 乱码，并会在捕获期触发 `seqused_k[0].item()` 的 `MUSA error: operation not permitted when stream is capturing`。
- **测速前必须先过正确性门**：temperature=0 跑十道算术（`17*23→391`、`2^14→16384`）+ 400 token 长文查 unique_ratio / 是否吐 0 或复读。判据看**最终答案**——别把合法中间量（`17×20=340` 里的 340）当崩坏；小模型 base 版自身算术弱（Qwen3-0.6B 恒 5/10，`7*8*9→408`）是**模型能力**不是 MUSA 故障。判"档位是否忠实"先对照同输入、同参数eager/graph原始输出及md5；一致只证明该样本重复性，不证明语义或任务正确，不一致须检查采样和数值误差而不能只凭hash归因。VLM要补不同图像/无图/错图对照；抓取要验证无weld、真实接触与保持，不能把轨迹/抬升当成功；再检查无握力与移除新增部件的双负对照、动态携带和保持。静态楔住、weld驱动或pad-off同样通过不能证明新增改造有效（见7A.4）。
- **roofline 判据**：单流 decode 受带宽 ⇒ 上限 ≈ 768GB/s ÷ 权重字节（7B BF16≈14GB ⇒ ≈**54 tok/s**；0.6B≈1.5GB ⇒ ≈500）。实测 7B 单流 30–35 tok/s = 56–66% 效率，合理；**54是特定精度、权重字节与带宽假设下的估算，不能作为绝对真假线**；超过时核查prefill/缓存、批量、权重精度与实际字节，不先断言测法错误。prefill 受算力：本节点 4096³ bf16 GEMM 实测 **75.7 TFLOPS**（规格 100 的 76%）。
- **选档**：交互式取 c≤8（7B 在 c=32 时 TTFT P99 已达 **3.6s**）；批处理/离线取 c=32 或 `vllm bench throughput`。7B 三档 output tok/s = **30.13 / 127.45 / 239.79**（c=1/8/32），stream 单流 35.45，离线 total 488.92。
- **权重下载**：ModelScope **28–33 MB/s** ≫ hf-mirror **4.2–5.2 MB/s**（并发分片 15GB 约 2–6 分钟）；`curl` 必须带 `-L`（不带只拿到 302 的几百字节，会误判源不通）；校验基准取 ModelScope manifest 的 sha256（hf-mirror 的 tree API 对 LFS 大文件不返 sha256）。
- **容器写法仍按 §6**：只设 `-e MTHREADS_VISIBLE_DEVICES=<卡号>`，禁 `all`、禁 `--privileged`（实测 privileged 会让容器看到 8 张卡、越界碰邻组）。

### 7A.4 出处与边界

报告（节点 reports/ 与主会话 server_reports/ 双留档，md5 两端一致）：`20260929-1830-qoder-vitfix-report.md`(`d8bccc07…`)、`20260929-1755-qoder-graph06b-report.md`(`841df3d9…`)、`20260929-1610-qoder-bench7b-report.md`(`32a59d16…`)、`20260929-1610-qoder-vl7-report.md`(`46bd727c…`)、`inference-selection-checklist-20260930.md`(`6fa31843…`)；探针原始数据 `logs/20260929-1830-qoder-vitfix/out/fa_probe_recheck_qoder.json`。
**截至本轮已核验研究状态（来源报告，本轮未重跑模型/仿真）**：

- VLM：vitfix2报告已更正num2words的3.10/3.11解释器分裂与BLIP长度4096→2048问题，不能再说“尚未补测”。Smol临时Conv2d绕过+视觉SDPA取得端到端结果，只有BIG有CPU原回答对照；BIG/SMALL同串、跨进程3/3重复不能证明辨图，ISS-VLM-IMAGE-DISCRIMINATION仍OPEN。BLIP warmup后HTTP500，OPT80维语言回退布局仍崩，视觉后端不能救语言；临时patch不作默认生产标准。来源reports/20260930-0238-qoder-vitfix2-report.md与Smol复测。
- 未解项：64/128误差来源、7B graph配置/正确性、多卡TP分别查issue和原证据；文档更新不代表已解。
- ARDY：reports/20260930-0245-qoder-fb32run-report.md确认b1=32、b2=0，来自bf16文本编码器按设计跳过，不是32次fp32错误回退。ISS-ARDY-FB32-COUNT剩计数命名/覆盖问题；4seed端到端CPU参照票决base32/fix12/平4不能宣称更准。teacher-forcing/分布级评估仍待，CPU同样穿透与MUSA精度分开。
- 抓取：reports/20260930-0414-qoder-graspfeas-report.md已完成1584run，A仅13个刀口静态格，pad-off复现且pad力0，动态B为0/746；旧“正在跑/縮方块加pad优先”不是当前首选。保留旧报告，真实几何/铰链与携带问题仍OPEN。
- SONIC：sonic/sonic_bridge/README.md自称第一版PyTorch桥接骨架；10-03 SSH审计记载安装/桥接开发及GLFW失败后转offscreen。可确认有源码与开发活动，不能说零落地，也不能说运行已验收；权重、obs/action映射与带日志smoke待属主核验。README来源/hash见本轮清单，不改其代码/环境。

研究待办统一查§4.6issue，旧文档/报告保留证据，接手优先看后补更正，不另造当前状态源。

## 8. 凭据与安全

- **绝不**把密码/token 写进命令行参数、md 文件、日志、脚本、`steps.md`。需要引用时写"见凭据文件"即可。
- 不尝试多次 SSH 密码登录（共享账号会被 fail2ban/PAM 锁定，锁的是全组 12 人）。
- 不 `git push` 到 main/master，不 `git push --force`，不动 `.git/config` 里的 remote。
- 需要免密登录时仅按§1.2明确授权的独立任务追加`~/.ssh/authorized_keys`，不重写。

---

## 9. 长任务与超时

- 单条命令不要超过 10 分钟；长下载/编译用后台方式：
  ```bash
  nohup <cmd> > "$BASE/logs/<TASKID>/dl.log" 2>&1 & echo PID=$!
  ```
  然后轮询 `du -sh` / `tail -c 400 dl.log` / `ps -p <PID>`。
- 轮询间隔不要超过 90 秒；不要盲目 `sleep`，也不要空转到超时。
- 进程收尾先核对自己的PID、启动时刻、命令、工作目录/容器ID；仅停止确认属于自己的遗留后台任务并记steps.md，禁止宽范围`pkill -f`或杀他人进程。**不要让别人接手时才发现一堆遗留进程**。
- 不要把长跑的中间结果只留在 `/tmp`（见 §1.3，重启即空）；落 `/home/group4/group4_dasc7606c/` 或写明重建方法。

---

## 10. 收工（①–⑥；完成、阻塞和交接如实区分）【锚点 AGENTS-FIX-20260930-B】

旧标题“三步/两步”与正文步数不符的更正历史保留在原版备份。本节合并done标记、journal、视图、自查、Git与双留档，避免两套收工顺序。

1. **报告与资源证据**：steps含失败，报告六段齐；普通实验确认进程退出/声明释放。常驻服务按§6分别记录部署与资源生命周期，明确运行属主/停止范围，不以部署完成宣称服务退出。
2. **未解决事项归并**：按§4.6查重补issue、重建校验问题视图；未部署/未实验注明，交接须承接人确认。
3. **首轮Git与双档**：按§3.4显式路径/独立身份提交，核其他暂存blob及快照截止；报告/必要证据在服务器与本地server_reports比hash。缺任一项就git/archive pending，不写新done，可用blocked如实登记。
4. **事件→校验→标记**：前置齐备才调用下方close入口done；blocked不新增done.txt。重试先查事件，已追加但后续失败补note/修复，不盲重复done、不删历史；既有done时间不覆盖。
5. **独立校验与视图**：检查journal返回码及正文、INDEX缺/多/行级差异；rc=0不等于视图/结论都正确。close成功已重建，仍滞后才再重建，不手写追加。
6. **收工增量归档**：新done/校验/视图尾部再显式Git、双档并记录截止；最后提交/归档结论不无限递归产新事件。增量没完对用户标post-close archive/git pending，不能说全部完成。

```bash
# 生产环境执行，先核对没有继承沙箱/跨目录的JOURNAL_BASE、GPU_BASE、JOURNAL、ANCHOR
BASE=/home/group4/group4_dasc7606c
unset JOURNAL ANCHOR
export JOURNAL_BASE="$BASE" GPU_BASE="$BASE"
# 前置：报告/issue/首轮Git/双档已核验；TASKID为自己的claim；CPU填“-”
: "${TASKID:?填写自己的任务号}" "${SUMMARY:?填写真实结论与数字}"
bash "$BASE/work/p0lock/close_ledger.sh" "$TASKID" - "$SUMMARY" done || exit 2
# 未完成改用blocked；不要随后手写done.txt
# bash "$BASE/work/p0lock/close_ledger.sh" "$TASKID" - "$SUMMARY" blocked
bash "$BASE/work/journal/tools2/journal_verify.sh" --base "$BASE"
# 退出码及输出都检查；需要刷新才用rebuild_index.sh
# append和rebuild内部共用journal.lock，顺序调用，不得外层同锁嵌套。
```

保留三条实测教训：INDEX是视图，不手写`>>`；账本用journal.lock而非占卡gpu.lock；append先于rebuild，两者同锁不得嵌套（曾自锁90s 超时）。`$(date)`在flock外算好，不嵌进双层引号写空ts。本次沿用上一轮已部署的close工具，不重新改写工具或部署cron。

---

---

> **每日账本体检（勿重复安装，标记QODER-JOURNAL-DAILY）**。05:35确认该行在位，最近04:17输出verify_exit=0且有完整校验正文，见logs/journal-daily/{20261003.log,history.log,cron.out}。在位不保证以后成功，须看最近日志及实际返回码。
> `17 4 * * *` 跑 `work/journal/tools2/journal_daily_check.sh`：`flock -n claims/journal.daily.lock` 独占 → 调 `journal_verify.sh` →
> 通过则往账本记一条 `journal-daily-check / note`；不通过则在仓库根生成 **`NOTICE-journal-<YYYYMMDD>.md`** 并记 `blocked` 事件。
> 日志：`logs/journal-daily/<YYYYMMDD>.log` + `history.log` + `cron.out`。
> **频率判据（为什么一天一次够）**：每日体检只是"没人守规矩时的兜底网"，真正的检测发生在**每个任务收工的 §10 ④⑤**；
> 且 `journal_append.sh` 每次写完会自检"锚点条数 == journal 行数"，不等就 **exit 6** 并拒绝收尾（09-30 实测：正向 0、负向 6）。
> 有效收工校验应尽早发现链/锚点错误；绕过流程后仅在日检真正执行并产出可判定结果时才有兜底。不能保证最长24h：cron可能停摆，记录是否真实也不是hash链能判断。
> 若要更紧，可把本行改成整点级（`0 * * * *`）——脚本是幂等的、有 `flock -n` 与 `journal.lock` 保护，加密度不改语义。
> 看见 `NOTICE-journal-*`：**先跑 `journal_verify.sh` 看退出码**（1=链断/锚点空洞，2=尾部截断，4=账本缺失），
> **两条硬约束（09-30 04:2x 假警报换来的）**：① **并发互斥只在 crontab 那一层做**——脚本内部**不得再 `flock` 同一个锁文件**，否则内层以 flock 自己的 **rc=1** 退出，而 1 恰好也是 verify 的"链断"码，于是天天报假案且 `verify` 根本没跑（现场特征：当日子节数为 0）。② 体检**只认三种结论**：verify 原码 0/1/2/4（有输出正文才算）、**8 = 工具没跑起来**（输出不可判定，去查 cron 与脚本而不是查账本）。看到 `NOTICE-journal-*.md` 先分辨属于哪一种：`8` 或代码块为空的都是工具故障，**不是账本被动过**。
> 只能**追加**修复（缺锚点补锚点行），**绝不改写或删除 `journal.log` 的历史行**。

## 11. 接手别人任务时

0. **先看开放问题登记簿**：`reports/open-issues.md`（视图，由 `claims/issues.jsonl` 重建）——里面写着"还没人做的事"和每条的具体接手动作；认领要登记 `handoff` 事件（见 §4.6）。
1. 先看`claims/INDEX.md`找最近的相关task-id；根`INDEX.md`仅历史兼容。再查journal的更正note与相关报告，普通note未必进入视图，不能假定已部署A_corrects。
2. 读它的 `logs/<TASKID>/steps.md` 和 `reports/<TASKID>-report.md`。
3. **只信带实测数字的结论**；看到"应该""大概""估计"要重新验证。
4. 验证结果若与前人报告冲突，在自己的报告里明确写"与前记录不一致 + 两边证据"，不要静默覆盖。

---

## 12. 冲突时的优先级

安全 > 队友文件不被破坏 > 不占别人 GPU > 任务进度 > 速度。

任何一条你判断不了的事，**停下来写进报告说明卡在哪**，不要凭猜测往下做。留一份说清问题的报告，比留下一堆无法解释的产物有价值。
