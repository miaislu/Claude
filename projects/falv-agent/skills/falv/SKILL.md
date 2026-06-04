# /falv — 中国法律 AI Agent 主入口

## 触发方式

```
/falv <子命令> [参数]
```

## 子命令路由表

| 子命令 | 功能 | 示例 |
|---|---|---|
| `shencha` | 合同全面审查（旗舰功能） | `/falv shencha 合同.pdf` |
| `fengxian` | 风险条款评分 | `/falv fengxian 协议.txt` |
| `hege` | 合规检查 | `/falv hege --type pipl` |
| `qicao` | 法律文件起草 | `/falv qicao --type 劳动合同` |
| `fanyi` | 法律术语转白话 | `/falv fanyi 条款.txt` |
| `laodong` | 劳动合同专项审查 | `/falv laodong 劳动合同.pdf` |
| `gongsi` | 公司法事务 | `/falv gongsi --type 股权协议` |
| `baogao` | 生成 PDF 报告 | `/falv baogao --last` |

## 执行指令

当用户输入 `/falv` 命令时：

1. **解析子命令**：识别第一个参数作为子命令名称
2. **路由执行**：将请求转发给对应的子技能（`skills/<子命令>/SKILL.md`）
3. **无子命令时**：显示上方路由表和使用示例，引导用户选择功能
4. **未知子命令时**：提示可用命令列表，询问用户意图

## 通用参数

- `--lang [zh|en]`：输出语言，默认 `zh`（中文）
- `--brief`：只输出摘要，不显示详细分析
- `--save <文件名>`：将报告保存为 Markdown 文件

## 注意事项

- 所有分析默认适用**中国大陆**法律体系
- 涉港澳台或跨境内容时，子技能会自动标注适用法域
- 每次输出末尾须包含免责声明
