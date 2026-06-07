# /legal report — 生成 PDF 报告

> 输出规范、法条引用要求和禁止行为见 `agents/_guidelines.md`。

## 功能描述

将最近一次 `/legal review` 或其他审查结果导出为格式化 PDF 报告，可供存档、分享或提交给律师参考。

## 用法

```
/legal report                          # 导出最近一次审查结果
/legal report --last                   # 同上
/legal report --file 报告名称.pdf       # 指定输出文件名
/legal report --include-suggestions    # 包含详细修改建议
```

## 参数

| 参数 | 说明 |
|---|---|
| `--last` | 使用最近一次审查结果（默认行为） |
| `--file <文件名>` | 指定输出 PDF 文件名，默认：`法律审查报告_YYYYMMDD.pdf` |
| `--include-suggestions` | 在报告中包含完整的逐条修改建议文本 |
| `--watermark <文字>` | 在 PDF 上添加水印（如"草稿"、"仅供参考"）|
| `--logo <图片路径>` | 在报告封面添加机构 Logo |

## 前置依赖

```bash
pip3 install reportlab
```

## 执行流程

1. 检查最近的审查结果是否存在
2. 调用 `scripts/generate_pdf.py` 生成 PDF
3. 输出文件保存路径

## 报告结构

生成的 PDF 包含以下页面：

1. **封面**：合同名称、审查日期、合同安全评分（大字显示）、免责声明
2. **执行摘要**：评分仪表盘、高危风险数量、合规状态一览
3. **详细分析**：按风险等级排列的条款分析表
4. **合规检查结果**：通过/未通过清单
5. **修改建议**（如有 `--include-suggestions`）：逐条原文 vs. 建议文本对照

## 执行指令

运行以下命令生成报告：

```python
python3 scripts/generate_pdf.py \
  --data <审查结果JSON路径> \
  --output <输出PDF路径> \
  --watermark "仅供参考" \
  --logo <可选>
```

生成完成后，告知用户文件保存路径，并提示：
"报告已生成：`法律审查报告_YYYYMMDD.pdf`  
⚠️ 本报告为 AI 辅助分析，不构成正式法律意见。"
