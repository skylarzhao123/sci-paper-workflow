# Codex、Hermes 与 ZCode 适配

## ZCode

1. 用户级技能位于 `~/.zcode/skills/<name>/SKILL.md`；如配置了 `ZCODE_DATA_BASE_DIR`，使用其指定的目录。当前会话可用 `$sci-paper-workflow` 显式调用；其他阶段 Skill 按名称加载，不能只写出名字就宣称执行。
2. 先读取本 Skill 的 `references/runtime.md` 和 `references/contracts.md`，到当前阶段时只读对应提示词。ZCode 的技能工具支持 Skill 名称；相对资源必须从该 Skill 所在目录读取。实际加载路径以 ZCode 列出的技能为准。
3. 需要的五个依赖 Skill 必须在 ZCode 可发现的目录中并处于启用状态。`~/.zcode/skills` 比通用导入位置优先；同名副本可能被高优先级副本遮蔽。不要以 Codex 或 Hermes 有安装作为 ZCode 已调用的证据。
4. 把依赖中的“当前 Codex 会话”解释为当前 ZCode Agent 会话。ARS 的角色提示按根入口的 inline 映射在当前会话执行。未经用户要求，不派生子代理、不运行跨模型或 Codex 专属传输。
5. 使用 ZCode 实际提供的文件、终端与网络工具执行步骤，不假设 Codex 或 Hermes 的工具名存在。检查材料和必要偏好时，直接在当前对话提问。
6. 状态检查用 `python3 "SKILL_ROOT/scripts/workflow.py" inspect --project "/absolute/project" --runtime zcode`，脚本只识别文件，不代替 ZCode 原生 Skill 加载。若结果与 ZCode 技能列表不同，以 ZCode 实际加载结果为准并记录差异。

安装后在 ZCode 的 Settings → Skills 点击 Refresh，确认六个 Skill 已启用。ZCode 官方说明：https://zcode.z.ai/en/docs/skill

## Hermes

1. `skill_view(name="sci-paper-workflow")` 加载总入口。记录返回的 `skill_dir`，将它作为命令中的 SKILL_ROOT；不要猜测安装位置。
2. `skill_view(name="sci-paper-workflow", file_path="references/03-draft.md")` 等形式加载当前阶段提示词。必要时先 `skills_list()` 查实际加载名称。
3. `skill_view(name="paper-skill")` 等形式加载该阶段依赖。相对资源通过 `skill_view(name="paper-skill", file_path="references/section-guides/experiments.md")` 读取。实际路径取返回的 `skill_dir` 或 `_source_path`。
4. 默认技能目录为 `${HERMES_HOME}/skills`，未配置时 `~/.hermes/skills`；可有 `research/` 等分类目录。命名 profile 的 HERMES_HOME 是该 profile 目录，不能静默回退到另一个 profile 来报告“已安装”。
5. 使用当前运行时提供的 terminal、文件读取、web_search/web_extract 等工具完成阶段。仅调用当前工具列表中存在的工具，名字不同时按等价能力适配。不要要求 Codex 专属函数才能继续。
6. 依赖中的“Codex agent/current Codex session”在这里解释为当前 Hermes 会话。ARS 的 Agent Team 按根入口的 inline 映射在当前会话执行；没有用户授权就不派生子代理、不跨模型发送材料，也不启动 Codex CLI/app-server。
7. 问题与输入检查直接在当前对话完成；无需 Codex 的 request_user_input 工具。用户已授权的任务不反复索要批准，必要事实与投稿偏好缺失仍需询问。
8. 状态脚本使用 `python3 "SKILL_ROOT/scripts/workflow.py" inspect --project "/absolute/project" --runtime hermes`。发现返回资源不完整时以原生 skill_view 的解析结果为准，记录真实路径，不虚报调用。

可用 `/sci-paper-workflow` 或自然语言“使用 sci-paper-workflow 继续论文项目”触发。不同客户端可能缓存索引；新会话可重新加载，不能为刷新技能擅自重置现有会话。

## Codex

使用 `$sci-paper-workflow` 或自然语言触发。读取系统列出的 SKILL.md 和必需资源；默认目录 `${CODEX_HOME}/skills`，未配置时 `~/.codex/skills`。inspect 可显式传 `--runtime codex`。

## 跨平台共同边界

两者执行相同阶段与提示词，按各自工具规则读写文件、核验来源。工具不可用时记录缺项。平台适配不改变证据、真实性或访问权限要求。状态记录含本机绝对路径，保存在论文项目中，不能提交到工作流源码仓库。

Hermes 官方说明：https://hermes-agent.nousresearch.com/docs/guides/work-with-skills/
