# Agent Navigator

简体中文 | [English](README.en.md)

> **让人的经验，持续参与 Agent 的执行。**

Agent Navigator 是一个本地、文件驱动、可被多种 Agent 读取的项目经验层。

它将人在长期人机协作中形成的观察、反馈、判断和方法，沉淀为可检索、可审查、可版本化的 Markdown，并让 Codex、Claude Code、Kiro 等 Agent 在后续相关任务中使用这些经验。

Agent Navigator 不是新的 Agent 运行时，也不替代你正在使用的编程 Agent。它负责在项目中建立一套公共的经验接口，实际任务仍由当前 Agent 完成。

[快速开始](#快速开始) · [投入实际使用](#在项目中投入实际使用) · [确认是否生效](#怎样确认-agent-已经采纳) · [工作原理](#工作原理) · [命令参考](#命令参考) · [完整文档](#进一步阅读)

---

## 为什么需要它？

一个长期项目能否真正做好，并不只取决于模型能力。人在与 Agent 协作时持续承担着重要工作：

- 观察 Agent 选择了怎样的理解和行动路径；
- 判断结果是否真正符合项目目标；
- 指出遗漏、错误、边界和风险；
- 认可有效方法，并逐步形成验收标准；
- 随着项目构建，积累只有真实执行后才会出现的经验。

这些经验是项目资产，却经常停留在人的脑中、聊天记录或某个工具的私有记忆里，难以持续参与后续执行。

Agent Navigator 建立下面的闭环：

```mermaid
flowchart LR
    A["Agent 执行"] --> B["人观察过程与结果"]
    B --> C["反馈、判断与验收"]
    C --> D["提炼可复用经验"]
    D --> E["项目经验层"]
    E --> F["相关经验进入后续任务"]
    F --> A
```

减少重复纠正可以是这个闭环带来的结果，但它不是项目的根本定义。更深层的目标是：

> **让人的经验从一次性的隐性判断，转化为能够长期帮助 Agent 执行的项目资产。**

---

## 核心思路：像 `git init` 一样开始

可以把 `agent-navi init` 理解成类似 `git init` 的初始化动作。

```text
git init
  → 在工作目录中建立 Git 仓库结构
  → 后续版本管理由 Git 工作流继续完成

agent-navi init
  → 在工作目录中建立经验层和 Agent 入口
  → 后续检索、执行与维护由 Codex / Kiro 等 Agent 继续完成
```

这个类比描述的是使用方式，而不是二者的内部实现完全相同。

`agent-navi init` 不会启动常驻服务，也不会替你执行项目任务。命令完成后会退出，留下 Agent 可读的项目文件。之后你继续正常使用 Codex、Claude Code、Kiro 或其他 Agent 即可。

| 参与者 | 主要职责 |
|---|---|
| CLI | 初始化目录、生成入口、同步文件、提供确定性的维护工具 |
| Agent | 理解当前任务、检索相关经验、完成工作、判断是否维护经验层 |
| 人 | 观察执行、评价结果、提供反馈、确认项目目标和边界 |

---

## 快速开始

### 1. 安装

当前版本需要 Python 3.10 或更高版本，没有第三方运行依赖。

克隆仓库后安装：

```bash
python3 -m pip install --user .
agent-navi --help
```

如果需要修改源码，可以使用 editable install：

```bash
python3 -m pip install --user -e .
```

安装后可以使用以下任一入口：

```bash
agent-navi --help
agent-navigator --help
python3 -m agent_navigator --help
```

### 2. 在项目工作目录中初始化

进入一个新项目或已有项目的根目录：

```bash
cd /path/to/your-project
agent-navi init --target .
```

也可以从其他位置指定目标目录：

```bash
agent-navi init --target /path/to/your-project
```

初始化会创建项目经验层：

```text
.agent-policy/
  current.md
  lessons.md
  heuristics.md
  playbooks.md
  inbox.md
  imports/
    raw/
```

并生成或同步不同 Agent 使用的入口：

```text
AGENTS.md
CLAUDE.md
.kiro/steering/agent-policy.md
```

这些入口告诉 Agent：经验文件在哪里、怎样选择相关经验、不同层级如何排序，以及什么时候值得维护经验层。

### 3. 用 Agent 打开同一个项目

确保 Codex、Claude Code、Kiro 或其他 Agent 的工作目录就是刚才初始化的项目根目录，然后像平常一样提出任务。

CLI 到这里已经完成了最主要的初始化工作。后续不需要为了每次任务重复执行 `agent-navi init`，也不需要让一个 Agent Navigator 进程一直运行。

---

## 在项目中投入实际使用

初始化文件只是第一步。Agent Navigator 的价值来自这些文件在真实工作中被读取、应用和维护。

### 第一次使用

启动一个位于目标项目根目录的 Agent 会话，然后直接提出真实任务。例如：

```text
请审查当前项目中的代码变更，说明审查范围、主要问题和验证结果。
```

如果当前 Agent 会自动发现 `AGENTS.md` 或对应的工具入口，它应该先读取入口，再根据任务从 `.agent-policy/` 检索相关经验。

不同 Agent、版本和运行方式的文件发现行为可能不同。如果你不确定它是否已经采纳，可以在第一次任务中明确告诉它：

```text
请先阅读项目根目录的 AGENTS.md，并将其中的指导纳入你的当前上下文。
然后根据当前任务，从 .agent-policy/current.md、heuristics.md、lessons.md
和 playbooks.md 中检索最相关的经验，再开始执行。
```

更短的提示也可以：

```text
阅读并将项目根目录的 AGENTS.md 注入到你的上下文中，然后继续当前任务。
```

这里的“注入”指的是让 Agent 读取并应用文件中的指导，不是启动额外的模型服务或修改模型参数。

### 在日常工作中

正常使用流程是：

1. 你向 Agent 提出真实任务；
2. Agent 读取入口，并检索少量与当前任务相关的经验；
3. Agent 完成当前工作；
4. 你观察过程和结果，给出纠正、认可、边界或验收反馈；
5. 当信号清晰、稳定且可复用时，Agent 在自然停顿处维护 `.agent-policy/`；
6. 后续相关任务再次检索这些经验。

```text
真实任务
  → Agent 执行
  → 人观察、反馈与判断
  → lesson / heuristic / playbook
  → 后续任务按需检索
  → 经验帮助 Agent 改进执行
```

用户通常不需要手工运行 `add-feedback` 或 `add-heuristic`。理解完整对话的 Agent 更适合判断一条反馈是否值得保存、适用于哪个范围，以及应该更新已有条目还是新增条目。

### 什么内容值得沉淀？

经验不只是错误纠正，也可以来自：

- 用户对某种结果或表达方式的明确认可；
- 多次任务中逐渐形成的验收标准；
- 工具执行后暴露的环境限制；
- 一条成功、失败或近似成功的行动路径；
- 任务范围、信息来源和风险边界的澄清；
- 已经稳定到需要固定步骤和检查点的工作流。

并非每轮对话都要写入经验层。一次性的要求、仍然含糊的判断和没有未来行为含义的信息，可以不写或暂时进入 `inbox.md`。

---

## 怎样确认 Agent 已经采纳？

生成入口文件不等于每一种 Agent 都会在每一种运行方式下可靠采纳。Adapter 是 Agent 层的指导，不是 CLI 的强制执行机制。

如果你不确定，可以直接询问：

```text
你是否已经读取并应用项目根目录的 AGENTS.md？
请列出本次任务实际使用的经验文件和相关条目标题，
并简要说明它们会怎样影响你的执行计划；不要加载无关内容。
```

如果还没有读取：

```text
请现在阅读项目根目录的 AGENTS.md，并将其中的指导纳入当前上下文。
再从 .agent-policy 中只检索与当前任务相关的经验，然后继续执行。
```

可以从三个层面观察是否生效：

1. **读取**：Agent 能说明它读取了哪个入口和哪些相关经验，而不是笼统声称“知道了”；
2. **应用**：经验实际影响了检索范围、检查顺序、计划或输出结构；
3. **维护**：真实任务形成稳定信号后，Agent 正确更新了最相关的经验条目。

如果项目使用 Git，也可以直接检查文件变化：

```bash
git diff -- AGENTS.md CLAUDE.md .kiro/steering .agent-policy
```

没有文件变化并不一定代表失败。只有当本轮形成了清晰、稳定、可复用的新经验时，才应该更新经验层。

---

## 一个具体例子

第一次代码审查中，Agent 只看了最新提交，遗漏尚未提交的修改。用户观察后指出：审查不能默认只覆盖最新提交，还要确认 staged、unstaged 和相关 untracked 文件。

Agent 可以把这次执行中形成的经验整理为：

```markdown
## Code review starts from repository state

Applies to: code review
Keywords: git status, unstaged changes, review scope
Source: user correction
Status: active

### Heuristic

Use repository state to decide review scope before assuming only committed
code matters.

### Search bias

Inspect staged, unstaged, and relevant untracked changes early.
```

在新的代码审查任务中，Agent 检索到这条经验后，可以更早确认完整范围。

这里的重点不只是避免重复犯错，而是把人通过观察一次真实执行形成的方法，保存为项目可以继续使用的经验资产。

---

## 工作原理

### 经验文件

| 文件 | 用途 |
|---|---|
| `current.md` | 当前项目指导和已启用的任务层 |
| `lessons.md` | 带背景、行动、结果和反馈的可复用经验 |
| `heuristics.md` | 改变未来检索、计划、行动或输出的弱引导 |
| `playbooks.md` | 已形成稳定顺序和检查点的项目工作流 |
| `inbox.md` | 暂时还不够清晰、稳定或完整的信号 |

### User / Task / Project 三层作用域

可选的用户层和任务层位于：

```text
~/.agent-policy/
  profile.md
  heuristics.md
  tasks/
    <task-id>.md
```

| 作用域 | 适合保存的内容 |
|---|---|
| User | 跨项目长期成立的个人偏好和边界 |
| Task | 代码审查、研究、文档比较等任务类型的方法 |
| Project | 当前仓库的约束、历史判断和项目工作流 |

用户层和任务层不会在 `init` 时复制进项目；它们只在检索时与项目层叠加。

优先级为：

```text
当前用户明确指令
  > 项目层指导
  > 显式或已启用的任务层
  > 用户层
  > 相关历史 lesson
```

当前用户指令始终可以覆盖历史经验。

### Agent 原生检索

Agent Navigator 不实现 embedding、向量数据库或语言专用的语义分类器。当前 Agent 使用自己的语义理解和文件检索能力，从经验层中选择少量与任务相关的条目。

`brief` 命令提供确定性的直接匹配辅助，适合长任务、调试或跨对话交接；它不是语义检索引擎，也不是日常使用的必要步骤。

### Agent 原生维护

CLI 只提供文件边界、精确替换、同步和轻量检查。是否值得写入、属于哪一层、应该合并还是新增，仍由理解当前对话和项目状态的 Agent 判断。

完整、低风险的项目 lesson 和 heuristic 可以由 Agent 在自然停顿处直接维护。范围不清、置信度低、风险高、指导冲突或涉及长期用户偏好时，应先询问用户。

---

## 与相邻方案的区别

| 方案 | 主要解决的问题 | 与 Agent Navigator 的关系 |
|---|---|---|
| Memory Bank | 项目是什么、当前做到哪里 | 可与行为经验层并存 |
| `AGENTS.md` / `CLAUDE.md` | 稳定项目指导和 Agent 入口 | 是 Agent Navigator 的第一层入口 |
| Kiro steering / skills / hooks | Kiro 内的指导、流程和自动化 | Kiro 可以消费同一经验源 |
| 数据库式 Agent Memory | 大规模事实存储与语义召回 | 目标和工程边界不同 |
| Hooks / CI / sandbox | 确定性执行和安全约束 | 承接不能只靠模型遵守的要求 |

对于规则很少、变化不大的小项目，一份高质量 `AGENTS.md` 可能已经足够。经验持续增长、需要保留形成背景、跨任务或跨工具复用时，分层经验层才更有意义。

---

## 命令参考

多数用户从 `init` 开始，之后让 Agent 在正常工作中维护经验层。其余命令主要用于高级设置、确定性操作或 Agent 辅助。

| 命令 | 作用 |
|---|---|
| `init` | 初始化项目经验层和 Agent 入口 |
| `init --global` | 初始化私有的用户层和任务层 |
| `setup --task <id>` | 在项目中启用一个明确的任务层 |
| `brief` | 生成当前任务的临时紧凑指导 |
| `sync` | 更新生成的 Agent adapter marker block |
| `add-feedback` | 确定性写入 lesson 或 inbox signal |
| `add-heuristic` | 确定性写入 project / task / user heuristic |
| `replace-entry` | 按精确 `##` 标题替换一个条目 |
| `import` | 导入原始资料并在 inbox 中记录 |
| `compact` | 生成 compact 草稿，不改写源文件 |
| `check` | 输出轻量任务提醒 |

常用示例：

```bash
# 初始化当前项目
agent-navi init --target .

# 初始化私有 user / task 层
agent-navi init --global

# 启用任务层
agent-navi setup --target . --task code-review

# 生成临时 brief
agent-navi brief --target . "review current code changes" --task code-review

# 同步入口文件
agent-navi sync --target .
```

`init --force` 会重新生成 adapter，但保留已经积累的项目经验 Markdown。`sync` 默认只更新生成标记内的内容，并保留文件中其他用户内容。

完整参数见：

```bash
agent-navi --help
agent-navi <command> --help
```

---

## 文件安全与边界

- 不需要数据库、服务器、MCP、模型 API 或常驻后台进程；
- 管理范围内的写入拒绝符号链接，使用逐文件锁和同目录原子替换；
- 临时 `brief.md` 和 compact 草稿默认不应提交；若 `brief.md` 已被 Git 跟踪，CLI 会拒绝覆盖；
- Adapter 是 Agent 行为指导，不是强制权限系统；
- 需要确定性保证的安全、权限、测试和发布要求，应交给 hooks、CI、sandbox 或权限系统；
- Candidate heuristic 默认不会进入正常检索，除非用户明确请求或专门检查。

Agent-authored policy prose 和描述性 metadata 默认使用英文，以提高跨工具和跨语言任务中的稳定性；文件路径、命令、符号和 API 名称保持原样。

---

## 开发

运行完整测试：

```bash
python3 -m unittest -v
```

CI 覆盖 Python 3.10 至 3.13。

项目和 Python 包名称为 Agent Navigator / `agent_navigator`，CLI 入口为 `agent-navi` 和 `agent-navigator`。

---

## 进一步阅读

- [文档索引](docs/README.md)
- [研究与思考过程](docs/research-and-thought-process.md)

研究与思考过程保留了项目背后的问题来源、理论分析和设计取舍。

---

## 引用与致谢

如果 Agent Navigator 对你的工作有所帮助，或者项目中的思路启发了你的研究、文章或软件项目，欢迎引用或注明本项目。

如果你将 Agent Navigator 集成、改造或用于自己的项目，也希望能在项目文档中保留一个指向本仓库的链接。引用、致谢和反馈能够帮助更多人了解这项工作，并推动相关思考与实践继续发展。

## License

[MIT](LICENSE)
