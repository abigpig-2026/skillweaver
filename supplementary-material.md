# 补充材料 — 论文 #1840

我们感谢审稿人提出的建设性问题与意见。本补充材料按五个小节（DATA-1 … DATA-5）组织，
每节对应一个或多个审稿问题。完整源代码见仓库：
https://anonymous.4open.science/r/skillweaver-B9F9/supplementary-material.md

| 小节   | 对应问题         | 内容                                                       |
| ------ | ---------------- | ---------------------------------------------------------- |
| DATA-1 | A-Q1, B-Q5, C-Q4 | UDG 构建、cycle-filtering 参数、cycle 枚举与去重、可扩展性 |
| DATA-2 | A-W2, C-W3       | UDG 构建推导（各依赖分量）                                 |
| DATA-3 | A-Q2, A-W3, C-W2 | live execution 稳定性（重复实验）                          |
| DATA-4 | A-W1, B-Q3       | 解析精度与 cycle 发现验证                                  |
| DATA-5 | B-Q4             | type label 与 name identifier 的 type compatibility        |

---

## DATA-1 — UDG 构建与 Cycle-Filtering 参数

### 1.1 边保留的三阈值机制

SkillWeaver 分三个阶段构建 *Unified Dependency Graph (UDG)*：(1) 为每个 skill 独立构建子图；
(2) 两两子图匹配以推导跨 skill 的边；(3) 组装全局加权有向图。两个动作节点之间的有向边
a_i → a_j 被保留，**当且仅当**三个阈值同时满足：

$$
t_{ij} \ge \tau_t \;\wedge\; c_{ij} \ge \rho \;\wedge\; \Phi(a_i,a_j) \ge \eta,
$$

其中 t_ij 为 type-compatibility（参数亲和度），c_ij 为 input completeness，Φ 为
组合依赖分数（见 DATA-2）。各参数的默认配置与作用：

| 参数                    | 符号 | 默认值 | 含义                                        |
| ----------------------- | ---: | -----: | ------------------------------------------- |
| type-compat 阈值        |  τ_t |    0.3 | 边的 type-affinity 下限                     |
| input-completeness 阈值 |    ρ |    0.3 | a_i 能满足 a_j 所需输入的最小比例           |
| dependency-score 阈值   |    η |   0.44 | 组合分数 Φ 的下限                           |
| input-match 阈值        |  τ_m |    0.3 | c_ij 中判定单个 input 被匹配的最小 `compat` |

这些阈值共同决定了哪些候选边能够存活，进而决定了能够发现哪些 cycles。论文主实验使用上述默认配置。

### 1.2 Cycle 枚举与去重过程

Cycle 在 action-node 级的 UDG 上枚举（论文 Algorithm 1）：

1. **构图** —— 在所有 action node 上构建 `networkx.DiGraph`，边权设为亲和度分数 Φ。
2. **强连通分量** —— 用 Tarjan 算法计算所有 SCC，保留规模 ≥ 2 的分量（简单环不可能跨越平凡 SCC）。
3. **Johnson 简单环枚举** —— 在每个保留的 SCC 上枚举 hop 数 k ∈ [min_hop=3, length_bound=6] 的简单环。
4. **按起点旋转去重** —— 同一 cycle 会从多个起点被枚举出来；我们把每个 cycle 旋转，使其字典序最小的节点 id 排在首位，再丢弃重复项。
5. **解析** —— 每个去重后的 cycle 被解析为 `CyclicPath`，携带其 skill 序列、逐边亲和度与平均语义相似度。

对大规模图提供了 per-SCC 批处理模式（逐个 SCC 处理并及时释放内存）。

### 1.3 多组参数设置的敏感性评估

我们分析最影响图密度的四个设计维度——依赖分数阈值 η、权重 α:β:γ、hop 边界
`(min_hop, length_bound)`、`max_unique_skills` 上限——覆盖全部 4 个场景。我们经验性地扰动 η 与权重
（作为**联合配置交叉扰动**：每个配置同时指定二者，见下表），同时单独审视 hop 与 unique-skill 这两个
固定约束（因物理意义固定而不扫描）。为把 η 与权重的影响从 stage-1 随机性中隔离出来，我们固定论文实验所用的 stage-1 parsing 输出
（即生成 Table I 所用的同一份 67 skills / 243 actions 清单），对每个扰动仅改变 η 与权重，直接
重新运行 UDG 构图与 cycle 枚举（保持已解析的 skill 与 action 不变）。下表报告的 cycle 数因此是
**直接观测值**，而非换算值。

**理论分析：为什么均衡三信号能避免单一信号占优。** 三个信号为依赖推断提供互补证据：type 兼容 t_ij
捕捉数据形式兼容，input 完整 c_ij 衡量必需输入的覆盖，语义相关 s_ij 帮助抑制与任务无关的匹配。由于
Φ 将三者组合，没有任何单一信号能单独保证一条依赖成立：

- **type（α）**：仅类型兼容无法确立语义应当流动。`type_score` 矩阵对"同类型"对（如 `string→string`、
  `file→file`）给最高分 1.0，而 `string` 是参数池中出现最频繁的类型——type 只反映"数据形式"相同，无法
  区分"这份 string 是否真是 a_j 想要的语义内容"，是一扇**宽门**：只滤掉类型明显冲突的边，却保留海量
  "类型对得上、语义无关"的噪声边。
- **semantic（γ）**：仅语义相关无法确立数据流连通。两个 skill 可能都提及 "email"，一个负责发送、一个
  负责归档，之间并无真实数据依赖。
- **completeness（β）**：c_ij 是一个 **gate**——一旦满足（c_ij→1）就不再贡献区分度，所有通过门的边在此
  信号上趋同。

均衡权重 (0.35:0.35:0.30) 迫使每条边同时利用三个信号、而非让任一信号单独占优；下方的敏感性结果进一步
表明，严重偏置某一信号会降低 retained-cycle 覆盖和/或 live 激活有效性。η 则是密度旋钮：η↓ 纳入更多
弱支撑边，而 η↑ 只保留更高分边、代价是覆盖下降。

**交叉配置与敏感性结果。** η 与权重是一个联合配置——每个可运行配置同时指定二者。我们围绕默认点
(η=0.44, 0.35:0.35:0.30) 做交叉扰动：单独下调/上调 η（权重不动），或单独偏置某一权重（η 不动）。对每个
配置，我们并列报告三个量：**retained-cycle 覆盖**（Retained cycles，在固定 stage-1 parsing 输出上直接重跑
UDG 构图与 cycle 枚举得到）与**抽样激活有效性**（固定 S1 + OpenClaw + Qwen3.5-Plus，抽样 20 cycle
做 live 执行的 AR 与成功 CAF）。由于 AR 与 CAF 只在 S1（n=20）上测得，而 Retained cycles 覆盖全部四场景，
我们因此**并列**报告三者，而非将其合并为单一乘积：

| 配置                      |    η | 权重 α:β:γ     | Retained cycles | AR (S1, n=20) | 成功 CAF |
| :------------------------ | ---: | :------------- | --------------: | ------------: | -------: |
| 默认（均衡）              | 0.44 | 0.35:0.35:0.30 |       **1,053** |           60% |    21.3x |
| η 下调                    | 0.40 | 0.35:0.35:0.30 |           1,137 |           55% |    19.1x |
| η 上调                    | 0.48 | 0.35:0.35:0.30 |             287 |           65% |    22.0x |
| α 偏置（偏 type）         | 0.44 | 0.45:0.30:0.25 |             214 |           20% |     7.8x |
| β 偏置（偏 completeness） | 0.44 | 0.25:0.40:0.35 |           1,053 |           50% |    18.5x |
| γ 偏置（偏 semantic）     | 0.44 | 0.30:0.35:0.35 |             269 |           25% |     9.8x |

**综合判断。** 并列看覆盖、AR、CAF 三者，默认配置在保留完整 1,053 cycle 覆盖的同时维持了较高的激活有效性
（AR 60%、CAF 21.3x），而每个被扰动的配置都在三者中至少牺牲一项：

- **α 偏置（偏 type）** 将 retained cycles 降至 214、AR 降至 20%，成功 CAF 为 7.8x，表明过度加权 type
  compatibility 会同时损害 cycle 覆盖与 live 激活有效性。
- **γ 偏置（偏 semantic）** 类似地将 retained cycles 降至 269、AR 降至 25%，成功 CAF 为 9.8x。
- **η 上调（0.48）** 虽因幸存者偏差 AR 略升到 65%、CAF 22.0x，但覆盖从 1,053 骤降到 287（漏报 73%）——
  把大量中等分数的边一并砍掉，得不偿失。
- **η 下调（0.40）** 多纳入 8% 的弱边（1,137），但弱边 cycle 可激活性差，AR 降至 55%、CAF 降至 19.1x——
  η 下调温和，但无增益。
- **β 偏置（偏 completeness）** 削弱了真正判别性的 type 信号、又得不到 c_ij（已饱和）的补偿，AR 降至 50%、
  CAF 18.5x。
- 响应**不对称**（下调温和 +8%、上调/偏置 α/γ 悬崖式 −73%~−80%）：下调 η 只温和地多纳入少量弱边，而上调
  （或偏置单一权重）会让高密度场景的边成片消失、其环随之崩溃。

综上，在所测试的配置中，默认参数 (η=0.44, α:β:γ=0.35:0.35:0.30) 在 retained-cycle 覆盖与 live 激活有效性
之间给出了均衡的取舍。三信号互补的作用为这一表现提供了定性解释。这是对所测试配置集合的经验观察，而非
对全局最优性的断言。

**hop 边界。** 我们将 hop 边界主要视为 scope 约束而非可调参数，并分别考察其边界选择：

- **下界 `min_hop=3`（排除 hop=2）。** hop=2 的环只包含两次 action 转移，代表直接成对交替（A↔B）。本文
  关注的是至少三个 action node/hop 的多阶段 loop；这不排除只含两个 distinct skill、但含三个或更多
  action stage 的 cycle。在这一范围内，hop=2 既不符合本文所针对的多阶段 loop，也不属于本文的攻击面，
  `min_hop=3` 是定义的要求而非可调旋钮。

- **上界 `length_bound=6`（排除 hop=7）。** 更长 hop 的环还会累积更多跨 skill 的输入/输出错配与语义
  漂移。注意 3–6 hops 是本文的 evaluation scope：RQ2 只在该范围内抽样候选，因此 live-execution 结果
  本身并不排除 7-hop 环被激活的可能。在这一范围内枚举可完成、语义可解释，故 6 是自然上界。

- **3–6 hop 已足以支撑结论。** 论文的 1,053 个 retained 候选 cycles 全部落在 hop∈[3,6]，深度呈长尾分布
  （k=4 占 57.5%、k=6 占 24.2%、k=3 占 10.4%，其余为 k=5），retained 候选闭环集中于中深度区间。报告的
  cycle-discovery 结果完全落在 3–6 hop 的评估范围内，hop=2 的边界排除（范围外的成对交替）不影响它。

**`max_unique_skills` 上界。** 该上界是有实质约束力的，而非空约束：将上界从 4 上调到 5，cycle 数不变
（1,053，因为没有任何保留 cycle 含 5+ 个 distinct skill）；但将上界从 4 下调到 3，会砍掉 486 个含 4 个
skill 的 cycle（S1 247、S2 169、S4 70），cycle 数降至 567（−46%）。因此上界 4 实际筛选出了构成组合式
攻击面的四 skill 闭环——它是实质性约束，而非对真实结构的事后确认。

### 1.4 可扩展性讨论

在论文规模（67 skills、243 action nodes、1,865 条保留边；Table I）下，完整 pipeline——Tarjan SCC
分解加上逐 SCC、逐 hop 的 Johnson 简单环枚举——在秒级内完成（4 个场景实测 0.4–18 s，含逐 SCC 释放
内存的批处理模式）。复杂度为 Tarjan O(V+E) 加上每个 SCC 内的 Johnson
O((V_s+E_s)(C_s+1))，其中 C_s 为该 SCC 的简单环数；在 `length_bound=6` 下，单层枚举为
O(V^6)，是常数次幂界，保证每一层都可处理。

真正的瓶颈是**图密度**而非节点数：当 η 过低时，高密度场景（千条边级）会使 cycle 数爆炸、超出
枚举上限。η 直接控制图密度，因此也影响枚举成本。
保护措施包括 (i) `length_bound=6`、(ii) 全局 η 阈值、
(iii) cycle 数溢出上限。若 skill 生态扩展到 10³+ skills，可用边剪枝（affinity top-k）或社区检测把
两两匹配从 O(N^2) 降到 O(N k)；分层的 `SkillSubGraph` / `global_action_nodes` 结构已预留该扩展点。

---

## DATA-2 — UDG 构建的详细推导

### 2.1 各依赖分量

对源动作 a_i（输出 O(a_i)）与目标动作 a_j（输入 I(a_j)），推导三个分量：

**Type affinity t_ij** —— 所有输出/输入参数对上的最大参数级兼容度：

$$
t_{ij} = \max_{p \in O(a_i),\, q \in I(a_j)} \mathrm{compat}(p, q),
$$

$$
\mathrm{compat}(p,q) = 0.6 \cdot \mathrm{type\_score}(p,q) + 0.4 \cdot \mathrm{name\_score}(p,q).
$$

**Input completeness c_ij** —— a_j 的*必需*输入中，能被 a_i 的某个输出满足（compat ≥ τ_m）的比例：

$$
c_{ij} = \frac{\left|\{ q \in I_{\mathrm{req}}(a_j) : \exists p \in O(a_i),\; \mathrm{compat}(p,q) \ge \tau_m \}\right|}{|I_{\mathrm{req}}(a_j)|},
$$

当 a_j 无必需输入时 c_ij=1。

**Semantic similarity s_ij** —— 基于动作描述、参数描述与周边 workflow context 的文本表示计算。
TF-IDF 余弦相似度用于度量这些表示之间的相似度，由 `TfidfVectorizer` 编码
（词 n-gram 范围 (1,2)、sub-linear TF 缩放、10000 维特征）。

### 2.2 组合

三个分量组合为依赖分数：

$$
\Phi(a_i, a_j) = 0.35 \cdot t_{ij} + 0.35 \cdot c_{ij} + 0.30 \cdot s_{ij}.
$$

权重 (0.35 / 0.35 / 0.30) 反映参数级 type compatibility 与 input completeness 是主要信号，
语义相似度则以略低的权重参与。

### 2.3 Type-compatibility 矩阵与 name 规则

`type_score` 是覆盖各 type label（由 stage-1 parser 提取）的手工软矩阵。未知类型采用降级策略而非硬
零值，以避免误删合法边：

| 输出 → 输入             | score |      | 输出 → 输入                         | score |
| ----------------------- | ----- | ---- | ----------------------------------- | ----- |
| string → string         | 1.0   |      | url → url                           | 1.0   |
| json → json             | 1.0   |      | file → file                         | 1.0   |
| number → number         | 1.0   |      | boolean → boolean                   | 1.0   |
| string → json           | 0.8   |      | json → string                       | 0.9   |
| string → url            | 0.7   |      | url → string                        | 0.9   |
| string → file           | 0.6   |      | file → string                       | 0.8   |
| number → string         | 0.8   |      | boolean → string                    | 0.7   |
| unknown → unknown       | 0.5   |      | unknown → {string,json}             | 0.4   |
| {string,json} → unknown | 0.4   |      | unknown → number / number → unknown | 0.3   |
| （其余任意对）          | 0.3   |      |                                     |       |

`name_score` 对（小写化后的）参数名采用三值规则：一个名字是另一个名字的子串时取 0.8，input 名的某个
词出现在 output 名中时取 0.5，否则取 0。

---

## DATA-3 — Live-Execution 稳定性（重复实验）

### 3.1 全量重复执行与复现性

论文 RQ2 在报告的多个 platform–model 配置上各执行一次攻击。针对重复实验，我们聚焦
OpenClaw + Qwen3.5-Plus 这一配置，把这 **110 个路径（S1:35, S2:20, S3:40, S4:15）在完全相同的设置下
各再执行一次**（相同平台、模型，每次都用全新 session），于是每个路径都有一对执行记录。下表报告每个场景
的论文 CAF 与 AR、本次重复执行中成功激活路径的 CAF（均值 ± 标准差）与 95% 置信区间：

**分场景（每个路径执行 2 次，CAF 基于成功激活的路径计算）：**

| 场景        | 路径数 | n_success | 论文 CAF | 本次 CAF (mean±std) |    本次 95% CI | 论文 AR | 本次 AR |
| ----------- | -----: | --------: | -------: | ------------------: | -------------: | ------: | ------: |
| S1 办公协作 |     35 |        18 |    21.1x |        17.23 ± 4.68 | [15.07, 19.39] |   51.4% |   51.4% |
| S2 内容创作 |     20 |        12 |    18.9x |        17.87 ± 3.05 | [16.14, 19.60] |   60.0% |   60.0% |
| S3 数据分析 |     40 |        14 |    22.4x |        19.37 ± 4.51 | [17.01, 21.73] |   35.0% |   35.0% |
| S4 客户服务 |     15 |        10 |    17.3x |        19.50 ± 6.56 | [15.43, 23.57] |   66.7% |   66.7% |

这里 n_success 是本次重复执行中成功激活的路径数（即完成至少一次完整闭环遍历的路径），因此本次 AR =
n_success / 路径数；论文 AR 是论文 Table II 报告的激活率。95% CI 按 mean ± 1.96·s/√n 在本
次 n_success 个成功路径上计算，它刻画的是成功攻击之间 CAF 的离散程度，**而非**单个路径 run-to-run 的
变异性。场景级 mean CAF 的变化反映在"论文 CAF vs 本次 CAF"两列（S1–S3 低 1.0–3.9x、S4 高 2.2x）。所有
报告区间均远高于 CAF=1，本次重复执行的 CAF 均值（17.23x–19.50x）与论文报告的放大（17.3x–22.4x）处于
同一放大量级：S1–S3 本次略低、S4 略高，属两次执行间观察到的 variation，不改变"跨 skill 闭环产生 17–22 倍
token 放大"的核心结论。

### 3.2 CAF 定义与失败运行的处理

我们报告的 CAF 是对*成功激活*的路径（即完成至少一次完整闭环遍历的路径）计算的，因为 CAF 衡量的是完整攻击 cycle 产生的资源
放大；失败运行可能在完成 cycle 之前的不同阶段中止，其 token 消耗难以作为 cycle-level amplification
直接比较。这与论文一致：论文报告的是触发（激活）闭环攻击的均值 CAF（Table II），而非对全部尝试的
平均。

---

## DATA-4 — 解析精度与 Cycle 发现验证

### 4.1 Stage-1 skill parsing 精度（I/O 提取）

Cycle 发现的第一阶段是 LLM 对每个 skill 的 `SKILL.md` 做 I/O 提取。我们在全部 **67 个技能**
（4 个场景）上，对照人工复核的 ground truth 衡量其 precision / recall / F1 / type-accuracy；该
ground truth 由三名标注者独立复核每个 skill、并以多数投票消解分歧得到。
一条 entry 计入 I/O 当且仅当该 skill 实际接收或产出它（含业务参数、凭证、环境变量、文件路径、URL）。

**总体**

| 指标          | Micro |
| ------------- | ----: |
| Precision     | 0.992 |
| Recall        | 0.808 |
| F1            | 0.891 |
| Type accuracy | 0.975 |

Micro 指标聚合全部 67 个 skill。我们只报告 micro（及分场景 micro）：按 skill 平均的 macro 会把分母不同
的 skill 混在一起（空提取 skill 的 precision 未定义），而 micro 已足以回答 extraction precision/recall
这一问题。

提取共得到 **398 条 entry**，其中 **395** 条正确、**3** 条错误；标注者补充了 **94** 条遗漏 entry。
正确 entry 中 type label 一致的有 **385/395** 条。

**分场景（micro）**

| 场景        | 技能数 | Precision | Recall |
| ----------- | -----: | --------: | -----: |
| S1 办公协作 |     17 |     0.984 |  0.803 |
| S2 内容创作 |     16 |       1.0 |  0.780 |
| S3 数据分析 |     19 |       1.0 |  0.842 |
| S4 客户服务 |     15 |     0.984 |  0.805 |

**空提取分解**

- **真·空（2）**：不存在数据 I/O，parser 正确地提取为空 —— `customer-feedback`、`customer-support`。
- **漏提（10）**：parser 返回空 schema，但实际存在 I/O（人工补充 54 条 entry）：
  `calendar-create`、`doc-translator`、`content-translator`、`social-media-ops`、
  `business-intelligence`、`dashboard-updater`、`faq-retriever`、`followup-scheduler`、
  `knowledge-searcher`、`satisfaction-survey`。

**逐技能明细**

| 场景 | 文件夹                      | 技能名                                     | #提取 | #正确 | #错误 | #补充 |     P |     R | Type acc |
| ---- | --------------------------- | ------------------------------------------ | ----: | ----: | ----: | ----: | ----: | ----: | -------: |
| s1   | `calendar-create`           | Calendar Planner                           |     0 |     0 |     0 |     4 |     — | 0.000 |        — |
| s1   | `calendar-query`            | caldav-calendar                            |    12 |    12 |     0 |     3 | 1.000 | 0.800 |    1.000 |
| s1   | `clipboard-manager`         | clipboard-manager                          |     7 |     7 |     0 |     1 | 1.000 | 0.875 |    1.000 |
| s1   | `data-analysis`             | data-analysis-reporting                    |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s1   | `doc-reader`                | tencent-docs                               |     6 |     6 |     0 |     5 | 1.000 | 0.545 |    1.000 |
| s1   | `doc-translator`            | PDFMathTranslate                           |     0 |     0 |     0 |     3 |     — | 0.000 |        — |
| s1   | `email-reader`              | EmailDigest Daily Email Summary for Agents |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s1   | `email-sender`              | python-agentmail-send-receive              |     4 |     2 |     2 |     6 | 0.500 | 0.250 |    1.000 |
| s1   | `email-writer`              | email-writer                               |    11 |    11 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s1   | `excel-wps-table-diagnosis` | excel-wps-table-diagnosis                  |     9 |     9 |     0 |     0 | 1.000 | 1.000 |    0.444 |
| s1   | `meeting-notes-pro`         | meeting-notes-pro                          |     9 |     9 |     0 |     2 | 1.000 | 0.818 |    1.000 |
| s1   | `ppt-generator`             | ppt-maker                                  |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    0.800 |
| s1   | `report-writer`             | work-report-writer                         |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s1   | `rss-reader`                | News                                       |     6 |     6 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s1   | `smart-file-organizer`      | file-organizer                             |     4 |     4 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s1   | `summarize`                 | summarize                                  |    10 |    10 |     0 |     6 | 1.000 | 0.625 |    1.000 |
| s1   | `todo-tracker`              | todoist                                    |    26 |    26 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `article-writer`            | writing-plans                              |     1 |     1 |     0 |     1 | 1.000 | 0.500 |    1.000 |
| s2   | `audio-synthesizer`         | jarvis-vocal                               |     7 |     7 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `blog-writer`               | Blog Writer                                |    12 |    12 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `content-translator`        | PDFMathTranslate                           |     0 |     0 |     0 |     4 |     — | 0.000 |        — |
| s2   | `content-writer`            | content-writer                             |     7 |     7 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `image-search`              | image-ai-kit                               |     4 |     4 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `ppt-generator`             | ppt-maker                                  |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `seo-keyword-researcher`    | seo-keyword-researcher                     |     8 |     8 |     0 |     0 | 1.000 | 1.000 |    0.625 |
| s2   | `social-media-ops`          | social-media-ops                           |     0 |     0 |     0 |    17 |     — | 0.000 |        — |
| s2   | `social-poster`             | social-poster                              |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `trend-analyzer`            | startup-idea-validator                     |     8 |     8 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `video-editor`              | audio-video                                |     7 |     7 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `video-editor-1`            | video-editor                               |    15 |    15 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s2   | `watermark-adder`           | image-processor                            |     1 |     1 |     0 |     1 | 1.000 | 0.500 |    1.000 |
| s2   | `web-scraper`               | Agent Browser                              |    11 |    11 |     0 |     5 | 1.000 | 0.688 |    1.000 |
| s2   | `wechat-publisher`          | wechat-content-creator                     |     8 |     8 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `alert-sender`              | email-writer                               |    12 |    12 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `anomaly-detector`          | inventory-anomaly-prediction               |    11 |    11 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `api-fetcher`               | data-quality-check                         |     5 |     5 |     0 |     1 | 1.000 | 0.833 |    1.000 |
| s3   | `business-intelligence`     | Business Intelligence                      |     0 |     0 |     0 |     6 |     — | 0.000 |        — |
| s3   | `chart-gen`                 | chartgen                                   |    10 |    10 |     0 |     1 | 1.000 | 0.909 |    1.000 |
| s3   | `competitor-analyzer`       | startup-idea-validator                     |     3 |     3 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `dashboard-updater`         | project-planning                           |     0 |     0 |     0 |     7 |     — | 0.000 |        — |
| s3   | `data-analyst`              | data-analyst                               |     8 |     8 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `data-cleaner`              | data-quality-check                         |     5 |     5 |     0 |     1 | 1.000 | 0.833 |    1.000 |
| s3   | `db-connector`              | data-analysis-reporting                    |     6 |     6 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `feature-extractor`         | vision-helper                              |     4 |     4 |     0 |     2 | 1.000 | 0.667 |    1.000 |
| s3   | `file-importer`             | pdf-markdown-converter                     |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `forecast-engine`           | ai-data-analyst-cn                         |     6 |     6 |     0 |     1 | 1.000 | 0.857 |    1.000 |
| s3   | `log-collector`             | data-quality-check                         |     5 |     5 |     0 |     1 | 1.000 | 0.833 |    1.000 |
| s3   | `report-generator`          | daily-business-report                      |    10 |    10 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `sql-query-reviewer`        | sql-query-reviewer                         |     6 |     6 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `transform-engine`          | pdf-markdown-converter                     |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s3   | `visualizer`                | MindMap                                    |     6 |     6 |     0 |     1 | 1.000 | 0.857 |    1.000 |
| s3   | `workflow-trigger`          | workflow-diagram                           |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s4   | `chatbot-handler`           | alicloud-ai-chatbot                        |     7 |     7 |     0 |     1 | 1.000 | 0.875 |    1.000 |
| s4   | `contract-reviewer`         | contract-review                            |     7 |     7 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s4   | `crm`                       | CRM                                        |     8 |     8 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s4   | `customer-feedback`         | customer-feedback                          |     0 |     0 |     0 |     0 |     — |     — |        — |
| s4   | `customer-profiler`         | customer-segmentation                      |     6 |     6 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s4   | `customer-support`          | Customer Support                           |     0 |     0 |     0 |     0 |     — |     — |        — |
| s4   | `email-reader`              | EmailDigest Daily Email Summary for Agents |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    0.800 |
| s4   | `faq-retriever`             | ima-skill                                  |     0 |     0 |     0 |     4 |     — | 0.000 |        — |
| s4   | `followup-scheduler`        | Calendar Planner                           |     0 |     0 |     0 |     4 |     — | 0.000 |        — |
| s4   | `knowledge-searcher`        | lexiang-knowledge-base                     |     0 |     0 |     0 |     2 |     — | 0.000 |        — |
| s4   | `lead-generation`           | lead-generation                            |     7 |     7 |     0 |     1 | 1.000 | 0.875 |    1.000 |
| s4   | `offer-drafter`             | contract-review                            |     8 |     7 |     1 |     0 | 0.875 | 1.000 |    1.000 |
| s4   | `response-generator`        | email-writer                               |    10 |    10 |     0 |     0 | 1.000 | 1.000 |    1.000 |
| s4   | `satisfaction-survey`       | Employee Survey                            |     0 |     0 |     0 |     3 |     — | 0.000 |        — |
| s4   | `solution-recommender`      | contract-review-agent                      |     5 |     5 |     0 |     0 | 1.000 | 1.000 |    1.000 |

### 4.2 端到端 cycle 发现精确率

**实验设置。** 我们在四个场景上端到端运行完整三段式 pipeline（LLM I/O 抽取 → UDG 构建 → cycle 枚举），
评估发现的候选 cycle 的语义可激活性（精确率）。

**候选枚举。** 论文 Table I 报告了四个场景的 UDG 构建与 cycle 发现结果：67 个技能、243 个 action 节点、
1,865 条保留边、1,053 个保留候选 cycle（由 4,476 个原始 simple cycle 经旋转去重过滤后得到）：

| 场景                    | 技能数 |  Action |        边 | 保留 cycle |
| ----------------------- | -----: | ------: | --------: | ---------: |
| S1 Office Collaboration |     17 |      34 |       195 |        397 |
| S2 Content Creation     |     16 |     157 |     1,311 |        184 |
| S3 Data Analysis        |     19 |      36 |       282 |        361 |
| S4 Customer Service     |     15 |      16 |        77 |        111 |
| **总计**                | **67** | **243** | **1,865** |  **1,053** |

**候选 cycle 的人工验证。** 三名标注者对这 1,053 个候选 cycle 进行独立人工判断，评估每条是否构成语义上
可激活的闭环（每个技能的产物恰好是下一个技能的工作对象，并回到第一个技能）。每名标注者依
统一 rubric 对每条 cycle 打标签——若闭环中每条边都构成真实数据依赖则判为*可激活*，否则判为*不可激活*。
每条 cycle 的最终标签由三名标注者的多数投票决定，分歧通过简短的共识讨论仲裁。
由于没有可激活 cycle 的穷尽式 ground-truth 集合可用，我们报告精确率（precision）而非召回率（recall）——
即被标注者确认为语义可激活的候选 cycle 占比：

| 场景                    | 保留 cycle |  有效数 |    精确率 |
| ----------------------- | ---------: | ------: | --------: |
| S1 Office Collaboration |        397 |     164 |     41.3% |
| S2 Content Creation     |        184 |      91 |     49.5% |
| S3 Data Analysis        |        361 |     116 |     32.1% |
| S4 Customer Service     |        111 |      61 |     55.0% |
| **总计**                |  **1,053** | **432** | **41.0%** |

各场景均存在有效 cycle。精确率在 S4（客户服务，55.0%）与 S2（内容创作，49.5%）最高，与其较短的
平均 cycle 长度（Table I 中 3.6 与 3.9 hop）一致；S1（41.3%）与 S3（32.1%）较低。论文的 case-study
cycle（`Blog Writer` ↔ `content-writer` ↔ `seo-keyword-researcher`）就在 S2 的有效 cycle 之中。

**解读。** pipeline 把原始 cycle 空间从 4,476 压缩到 1,053 个保留候选，其中标注者确认 432 个（41.0%）
语义可激活——表明 pipeline 在全部四个场景中都识别出一批实质性的、语义可激活的 cycle。S4 与 S2 较高的
精确率与其较短的平均 cycle 长度相伴出现，尽管场景特有因素也可能有所贡献。这些结果表明 SkillWeaver 在
全部四个场景中都识别出语义可激活的跨 skill 闭环，其中抽样的子集随后在 live execution 中评估其资源放大效应。

---

## DATA-5 — Type Label 与 Name Identifier 的 Type Compatibility

在自然语言描述的 skill 中，**type label** 反映参数在*数据形式*上的兼容性，而 **name identifier**
在类型信息不足时补充参数的*语义角色*。我们通过受控实验量化验证这一点：将一组信号与人工标注的
参数对兼容性 ground truth 进行对比打分。

### 5.1 实验设置

从复核后的最终 I/O ground truth（67 个技能）构造全部 **192 output × 297 input = 57,024 个参数对**。
对每一对，**三名标注者**独立判断 output 的值能否直接作为 input 的合法数据传入（无需转换），依据参数语义判定；
最终标签由三名标注者的**多数投票**决定，与 DATA-4 的标注规范一致。我们在六层 `type_band × name_band` 上按固定 seed 分层采样 **501 对**，并在统一规范下标注。

**比较的信号** —— 5 个通用 baseline 与论文的 3 个信号：

| 信号                 | 定义                                     |
| -------------------- | ---------------------------------------- |
| `exact_type_match`   | 两个 type 字符串相等则 1，否则 0         |
| `char_ngram_jaccard` | 名字的 char 3-gram Jaccard               |
| `levenshtein`        | 名字的归一化编辑相似度                   |
| `tfidf_cosine`       | 名字的 TF-IDF (1,2)-gram 余弦            |
| `word_jaccard`       | 分词后名字的 word-set Jaccard            |
| `type_score`         | 论文的手工 type 矩阵                     |
| `name_score`         | 论文的子串 / 词匹配规则                  |
| `compat`             | 论文的 `0.6·type_score + 0.4·name_score` |

每个信号对二元标签打分，用 **AUC**（主指标）与 **Spearman 秩相关**（辅指标）评估。

### 5.2 结果

在 **501 对**（38 兼容 / 463 不兼容，base rate 0.076）上：

| 信号                 |       AUC | Spearman |
| -------------------- | --------: | -------: |
| `exact_type_match`   |     0.853 |   +0.400 |
| `char_ngram_jaccard` |     0.851 |   +0.381 |
| `levenshtein`        |     0.844 |   +0.315 |
| `tfidf_cosine`       |     0.575 |   +0.283 |
| `word_jaccard`       |     0.898 |   +0.499 |
| `type_score`         |     0.867 |   +0.362 |
| `name_score`         |     0.810 |   +0.335 |
| `compat`             | **0.933** |   +0.404 |

- **各自具有判别力。** `type_score`（AUC 0.867）超过硬相等 baseline `exact_type_match`（0.853）：
  软 type 矩阵捕获了二元相等所遗漏的形式兼容。`name_score`（AUC 0.810，远高于 0.5）表明 name
  identifier 确实携带语义角色信息。
- **组合取得最高 AUC。** `compat = 0.6·type + 0.4·name` 达到 **AUC 0.933**，为八个信号中最高 ——
  type 过滤不可调和的形式冲突，name 在形式本身歧义时确定语义角色同一性。
- **TF-IDF 相似度在短参数名上表现差。** `tfidf_cosine` 退化到 0.575（≈ 随机）：参数名是单个短标识符，词级 TF-IDF
  几乎找不到共享词汇、向量近乎正交 —— 这正是 SkillWeaver 使用*结构化* type/name 信号的原因。
- **关于 `word_jaccard` > `name_score`。** `word_jaccard`（0.898）本身也是一个*名字*信号，其 AUC 略
  高于粗粒度的三值 `name_score`（0.810），这反而印证而非否定了 name identifier 的价值；把
  `name_score` 细化为连续形式是未来方向，不改变此处的任何结论。

### 5.3 对标注口径的稳健性

裸 `content`/`text` 输入 vs. 领域特定输出（如 `email_content`）存在边界标签。我们在两种更严格口径下重打分：

- **drop-annotator**（leave-one-annotator-out）：每次移除一名标注者、用剩余标注者的一致判定重新打分，以确认 AUC 不依赖某一名标注者的判断。
- **flip-generic**：把每一对"仅因 generic 类型（`content`/`text`）被当作兼容"的判定翻转为*不兼容*后重新打分，以确认 AUC 不依赖 generic-type 的宽松捷径。

| 信号               | 完整 AUC | drop-annotator | flip-generic |
| ------------------ | -------: | -------------: | -----------: |
| `exact_type_match` |    0.853 |          0.819 |        0.829 |
| `word_jaccard`     |    0.898 |          0.891 |        0.869 |
| `type_score`       |    0.867 |          0.851 |        0.850 |
| `name_score`       |    0.810 |          0.825 |        0.788 |
| `compat`           |    0.933 |          0.925 |        0.911 |

所有口径下排序稳定：`compat` 始终最高，`type_score` 始终高于 `exact_type_match`，`name_score` 始终远高于随机水平。
