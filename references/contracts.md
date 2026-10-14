# 项目与运行记录

## 文件契约

沿用指南中的七类文件，增加进度目录。用户有既定名称时可在记录中映射，不强制改名。

| 文件 | 内容检查 |
|---|---|
| `question.md` | 研究对象、情境、可回答问题、比较机制/假设、研究类型、范围、未决决定；已知与假设分开 |
| `evidence-card.md` | 共识、分歧、证据空缺；每条 E-ID、判断、来源/年份/DOI或链接、原文位置、证据深度、核验状态 |
| `results-summary.md` | 只转录实际结果；R-ID、来源位置、样本量、组别、数值、单位、方向、统计表达（提供哪些写哪些）、缺项 |
| `paper-map.md` | 各小节问题、允许主张、E/R/图表 ID、缺项、交付文件，适配真实研究类型 |
| `drafts/` | 独立章节版本和修订记录，保持真实数值与引文键；完成/待补部分明确区分 |
| `claim-audit.md` | C-ID、版本/段落/句子位置、原句、主张、证据、支持程度、修订句、未决问题、修订后检查 |
| `citation-audit.md` | 文献身份、内容支持、撤稿检查分别记录；网络/全文不可用保持可见 |
| `journal-pool.md` | 用户偏好来源、顺序、范围匹配、文章类型、要求、OA/APC、风险/未知、官网链接、实际查询日期 |

`drafts/manifest.json` 是当前章节版本索引，例如：

```json
{
  "sections": {
    "Introduction": {"file": "drafts/01_introduction_v1.md", "status": "complete"},
    "Methods": {"file": "drafts/02_methods_v1.md", "status": "partial", "missing": ["实验温度"]}
  },
  "manuscript": null
}
```

示例中的内容只是格式演示。合稿后才填写实际 manuscript 路径。审计后的稿件另外保存，不修改第 3 阶段输入版本。

## 记录协议

每次执行前，把真实展开的提示词写入 `.paper-workflow/prompts/<stage>-<unique>.md`；变量从材料/已知约束填充，未提供项注明“未提供”，明确输入文件与允许范围。

阶段结束后创建 receipt JSON，运行 `record` 将记录保存至 `.paper-workflow/history/` 并更新 `state.json`。格式示例：

```json
{
  "stage": "draft",
  "status": "partial",
  "depends_on": ["outline"],
  "inputs": ["paper-map.md", "results-summary.md", "evidence-card.md"],
  "outputs": ["drafts/03_results_v1.md", "drafts/manifest.json"],
  "resources": ["/absolute/skills/paper-skill/SKILL.md"],
  "prompt": ".paper-workflow/prompts/draft-unique.md",
  "checks": ["逐项对照结果表，未新增数值和显著性判断"],
  "blockers": ["Methods 尚缺实验条件"],
  "notes": "Results 完成；其他章节继续按 manifest 处理。"
}
```

不得复制示例中的完成声明。`checks` 写真实执行的内容检查；关键缺失、矛盾、未核验主张列入 blockers。

- `stage`: question / outline / draft / audit / journal。
- `status`: partial / blocked / complete。完整五步任务存在章节缺项时 draft 不能完成；仅完成单节任务时记录 partial 并在 notes 说明本次范围已完成。
- `depends_on`: 实际依赖的已记录阶段，可空；必须存在。标 complete 时，依赖也必须为有效 complete。直接审计现有稿件无需制造前三步记录。
- `inputs`/`outputs`: 实际文件，项目相对路径或绝对路径。输入可在项目外；输出和 prompt 必须在项目内。每次列出完整有效产物集合，不能遗漏前轮仍使用的产物。
- `resources`: 实际读取的 Skill、阶段模板和所需资源的绝对路径。安装存在不等于已调用。阻塞且未调用时可空。
- `prompt`: 保存的完整任务提示词，不能只指向未展开模板。
- `checks`: 实际内容检查；哈希检查不等于科学核验。
- `blockers`: 阻止该阶段完成的事项；complete 必须为空，blocked 必须说明原因。

输入/输出/资源/prompt 内容变化都会标 stale；依赖阶段变更也会向下游传播。复查后保存新版本并重新记录。旧稿及记录保留。

首次接手已有论文，按实际任务从 draft/audit/journal 开始，设置真实 inputs 和 `depends_on: []`，不得伪造历史调用。脚本只提供机械性状态，阶段内容与既有稿件需由 Codex 阅读判断。

并发写入会被锁拒绝；遇到 `.paper-workflow/.lock` 先判断另一任务是否仍在写，不自动删锁。本流程顺序执行，无需后台轮询。
