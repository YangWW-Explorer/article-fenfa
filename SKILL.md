---
name: fenfa-sop
description: 将项目目录中的 Obsidian Markdown 长文导出为可粘贴到 MDNice 的公众号 Markdown，以及可复制到 X Articles 草稿箱的富文本 HTML。用户提到分发长文、公众号排版、MDNice、X Article、Twitter Article、Obsidian 文章双格式导出或手动发布稿时使用。默认只做格式适配，不改写观点，不自动发布。
---

# 长文双格式分发

把一篇已经定稿、已经插好图片的 Obsidian 长文转换成两个本地发布文件：

1. `36_公众号mdnice_<主题>.md`
2. `37_XArticle_<主题>_富文本粘贴版.html`

默认不扩写、不缩写、不拆成 thread，不调用浏览器，不上传平台。除非用户明确要求，否则不要改变标题、观点、案例、数字和段落顺序。

## 开工前检查

1. 读取仓库根目录 `README.md`，以其中的目录与命名规则为准。
2. 确认输入文件位于 `10_项目/<日期_主题>/`。找不到所属项目时先询问，不要新建项目。
3. 读取 [references/export_contract.md](references/export_contract.md)。
4. 扫描所有图片引用。只接受可公开访问的 `https://` 图片链接。

支持识别以下输入：

```md
![[本地图片.png]]
![说明](./本地图片.png)
![说明](https://image-host.example/image.png)
```

前两种是本地引用，不能直接用于公众号或 X。发现任一本地引用时，停止导出，逐项列出原引用；不要猜图床地址，不要静默删图，也不要生成残缺的发布稿。

## 执行导出

使用 Skill 自带脚本：

```bash
python3 _agent/skills/fenfa-sop/scripts/export_manual_distribution.py \
  "10_项目/<日期_主题>/<母版>.md"
```

主题识别不准确时显式传入：

```bash
python3 _agent/skills/fenfa-sop/scripts/export_manual_distribution.py \
  "<母版>.md" --topic "<主题>"
```

脚本执行以下确定性操作：

- 删除 YAML frontmatter、HTML 编辑备注和正文水平分隔线。
- 保留正文内容、标题层级、粗体、斜体、列表、引用、链接和图片顺序。
- 把公众号图片统一为 `![说明](https://...)`。
- 生成带“复制富文本”按钮的 X Article HTML。
- 已有同名文件时生成 `_v2`、`_v3`，不覆盖人工修改；只有用户明确要求时使用 `--overwrite`。

## 输出验收

### 公众号 MDNice

- 文件是纯发布稿，无 frontmatter、编辑备注、配图占位符和使用说明。
- 所有图片均为 `https://` Markdown 图片链接。
- 正文没有独立成行的 `---`、`***`、`___`。
- 整篇可直接复制进 MDNice。

### X Articles

- 用 Chrome 打开 HTML，点击“复制富文本”，再粘贴到 X Articles 编辑器。
- 保留标题、小标题、粗体、列表、链接、段落和远程图片位置。
- X 是否接收剪贴板中的远程图片由平台编辑器决定。若平台忽略图片，明确告诉用户必须逐图上传；不要声称换一种文件格式就能绕过平台限制。
- 只保存到草稿箱；除非用户明确要求，不自动发布。

## 写入与备份纪律

- 两个输出文件只写在母版所在的项目目录，保持平铺。
- 排版变体不写入 `20_文案库/`。
- 项目完结且用户逐项确认后，才按根目录 `README.md` 复制最终长文到 `20_文案库/文章/`。
- 不在项目目录中创建分发子目录。

## 失败条件

遇到以下任一情况时停止并报告：

- 输入文件不存在或不在项目目录。
- 图片是 Obsidian、本地绝对路径、相对路径、`file://` 或非 HTTPS 链接。
- 正文仍有 `[截图位]`、`【配图待补】` 等占位符。
- 目标文件需要覆盖，但用户没有明确授权。

