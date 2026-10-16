# SCI Paper Workflow

供 **ZCode、Hermes Agent 与 Codex** 使用的五步论文工作流：定问题 → 搭架子 → 分节写 → 核主张并润色 → 定期刊。

由当前智能体按阶段读取对应 Skill 和提示词，并用文件传递证据与结果。Python 脚本只管理本地进度和依赖变化，不自行调用模型或后台运行。

| 阶段 | 调用的 Skill | 产物 |
|---|---|---|
| 定问题 | academic-research-suite（ARS-Codex） | question.md、evidence-card.md |
| 搭架子 | paper-skill | results-summary.md、paper-map.md |
| 分节写 | paper-skill 与章节指南 | 独立版本章节稿、合稿 |
| 主张审计与润色 | ref-verify → anti-defensive-writing | claim-audit.md、citation-audit.md、修订稿 |
| 选刊 | journal-recommender | journal-pool.md |

## 安装到 Hermes

需要 Python 3.10+。先将公开仓库克隆到固定位置：

```bash
git clone https://github.com/skylarzhao123/sci-paper-workflow.git
cd sci-paper-workflow
python3 scripts/install_local.py --target hermes
```

此命令只安装工作流，不下载依赖。如本机 Codex 已有五个依赖，可在首次安装时改用：

```bash
python3 scripts/install_local.py --target hermes \
  --dependency-root "$HOME/.codex/skills"
```

默认复制，遇到既有技能会停止，不覆盖它。要共享现有目录而不复制，可在首次安装命令增加 `--mode link`；此时必须保留源目录。命名 profile 可传 `--skills-dir "/absolute/profile/skills"`，或在正确的 `HERMES_HOME` 下运行。

依赖尚未安装时，可先使用 Hermes Skills Hub：

```bash
hermes skills install Imbad0202/academic-research-skills-codex
hermes skills install cLin-c/paper-skill
hermes skills install Kiterlin/anti-defensive-writing/skill/anti-defensive-writing
hermes skills install Moonweave-Research/ref-verify
hermes skills install zero565656/journal-recommender
```

以上命令由平台执行正常安装检查，获取的是上游当前版本；本项目测试时的版本记录见 [依赖来源](references/dependencies.md)。不要求重装已存在的依赖，也不在本仓库打包第三方 Skill。

在 Hermes 中说：

```text
/sci-paper-workflow 论文材料在 /absolute/project，请判断当前阶段，自动调用对应 Skill 和提示词推进。
```

也可自然语言调用。当前客户端未刷新索引时，在新会话中使用；无需清除已有会话。

## 安装到 Codex

```bash
python3 scripts/install_local.py --target codex
```

依赖通过各项目安装说明或 Codex 的 skill-installer 安装。在对话中使用：

```text
使用 $sci-paper-workflow。我的材料在 /absolute/project，请从适合的阶段继续。
```

## 安装到 ZCode

ZCode 使用用户级目录 `~/.zcode/skills`。本机 Codex 已安装五个依赖时，运行：

```bash
python3 scripts/install_local.py --target zcode \
  --dependency-root "$HOME/.codex/skills"
```

安装会复制本 Skill 和五个已有依赖；若目标目录已有同名 Skill，会停止并保留原件。没有 Codex 依赖时，先按[依赖来源](references/dependencies.md)获取各 Skill，或直接将各 Skill 安装至 ZCode 用户技能目录。随后在 ZCode 的 Settings → Skills 点击 Refresh，确认六个 Skill 已启用。调用示例：

```text
$sci-paper-workflow 论文材料在 /absolute/project，请判断当前阶段并继续。
```

ZCode 的原生调用与目录要求见[官方说明](https://zcode.z.ai/en/docs/skill/)；平台差异见 [runtime.md](references/runtime.md)。

## 进度与恢复

```bash
python3 scripts/workflow.py init --project /absolute/project
python3 scripts/workflow.py inspect --project /absolute/project --runtime hermes
```

阶段执行后，智能体按 [记录协议](references/contracts.md) 写 receipt，再调用 record。记录包含输入、输出、实际使用资源和提示词的 SHA-256；文件或上游记录变化时下游标记 stale，要求复查受影响内容。

可从已有稿件直接进入审计或选刊；缺真实数据时保留 partial/blocked，继续独立可做的工作。科学真实性由实际材料核对保证，状态脚本不会自动证明结论正确。

## 测试与内容边界

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

测试覆盖状态恢复、变更传播、路径检查和本地安装；不代表论文质量或录用结果。真实研究数据、稿件、凭据以及包含绝对路径的进度记录都保留在各自论文项目中，不提交到此仓库。

五步流程参考用户提供的全息学术笔记《刚刚，ChatGPT 6 一口气写完两篇SCI论文》（2026-09-14）：[原文](https://mp.weixin.qq.com/s/tpnGYLf4KE6j-8tGs-ELQQ)。本仓库提供重新组织的调度规则、提示词与状态代码，不包含原文 PDF。依赖工具及其许可证归各自项目所有。

Hermes 加载方式依据[官方技能指南](https://hermes-agent.nousresearch.com/docs/guides/work-with-skills/)；具体运行映射见 [runtime.md](references/runtime.md)。
