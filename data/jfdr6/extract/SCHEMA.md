# 9分达人听力6 PDF 提取中间格式规范

所有提取产物放在 `data/jfdr6/extract/` 下。页面图片在 `data/jfdr6/pages/page-{NNN}.jpg`（NNN = PDF 页码，三位补零）。页码地图见 `data/jfdr6/page_map.json`。

通用规则：
- 忠实转录书面内容：保留原始大小写、标点、拼写；不要"改写/纠错"。
- 题号使用全卷编号（Part 1 = Q1-10，Part 2 = Q11-20，Part 3 = Q21-30，Part 4 = Q31-40）。
- JSON 一律 UTF-8、缩进 2 空格（transcript 用 jsonl，每行一个对象）。

## 1. `test{N}/part{S}.questions.json` — 真题题目

```json
{
  "test": 1,
  "part": 1,
  "groups": [
    {
      "type": 5,
      "title": "Enquiring About Community Centre Classes",
      "question_title": "",
      "desc": "Questions 1-10\nComplete the notes below.\nWrite ONE WORD AND/OR A NUMBER for each answer.",
      "collect": "…填空题干，空格写成 $1$ $2$…",
      "table": null,
      "collect_option": {"title": "", "list": null},
      "questions": [
        {"number": 1, "title": "Course begins in: 【   】", "options": []}
      ],
      "needs_image": false,
      "image_pages": []
    }
  ]
}
```

### type 题型码（与现有剑桥数据一致）
| type | 题型 | 关键字段 |
|---|---|---|
| 1 | 单选 (Choose the correct letter, A, B or C) | 每题 `title` + `options: [{"title":"A","content":"…"}]` |
| 2 | 多选 (Choose TWO letters A-E，两题共享一组选项) | group 级 `collect_option.list: [{"title":"A","content":"…"}]`，questions 的 title/options 留空 |
| 3 | 表格填空 | `table: {"title":"", "content": [["单元格",…],…]}`，空格在单元格内写 `$N$`，表头单元格用 `<b>…</b>` |
| 4 | 简答 (Answer the questions below) | 每题 `title` = 问句 |
| 5 | 笔记/句子填空 | group `collect` = 完整题干 HTML（换行 `\n`，加粗 `<b>`，空格 `$N$`）；同时每题 `title` = 含该空的那一行，空格写成 `【   】` |
| 6 | 流程图/图示填空 | 需要截图：`needs_image: true` + `image_pages` |
| 7 | 地图/平面图标注 | 需要截图；每题 `title` = 地点名 |
| 8 | 选项箱配对 (词库选择填空/matching) | group `collect_option.list` + 每题 `title` = 被配对项 |
| 9 | 单题多选 (Which TWO … 一个题号选两个字母) | 选项放在题目自身 `options` |

- 空的 `collect_option` 统一写 `{"title": "", "list": null}`；空 `table` 写 `null`；空 `collect` 写 `""`。
- 地图/图示题（type 6/7）：不裁图，只标 `needs_image: true` 和图所在 PDF 页码，后续统一截图。

## 2. `test{N}/part{S}.transcript.jsonl` — 听力原文（逐句一行）

```
{"idx": 0, "speaker": "Assistant", "en": "Hello, this is Preston Community Centre.", "q": []}
{"idx": 1, "speaker": "Man", "en": "Oh, hello. My name's Andrew Shepherd. I'm ringing about the classes you offer.", "q": []}
```

- **切句**：按书面句号/问号/感叹号切分为独立句子；一个说话轮次(turn)含多句时拆成多行，同一 speaker 重复标注。保护缩写（Mr. / Dr. / a.m. / e.g. 等）不误切。
- `speaker`：照抄书中说话人名（如 Assistant / Man / Tutor / Jeannie）；独白（无说话人标签，常见于 Part 2/4）写 `""`。
- `q`：**书中带下划线且页边标注 Q 题号的句子**，把题号写入数组（如 `[3]`）。下划线跨多句 → 每句都写；一句对应多题 → `[21, 22]`。无标注写 `[]`。
- 书中题段之间的虚线分隔行（-----）跳过，不产生记录。
- `idx` 从 0 连续递增，不留空洞。

## 3. `test{N}/part{S}.analysis.json` — 真题解析

```json
{
  "test": 1,
  "part": 1,
  "items": [
    {
      "number": 1,
      "answer": "morning",
      "analysis": "听前预测：定位词…\n题目解析：…"
    }
  ]
}
```

- `answer`：解析标题 "Question N 答案 X" 里的 X，原样照抄（可能含多个可接受形式，如 "5(th) May/May 5(th)"）。
- `analysis`：该题解析正文全文（含"听前预测"与"题目解析"两段，段间用 `\n`），保留中英混排原文。

## 4. `answer_key.json` — 答案总表（全书一份）

```json
{
  "1": {"1": "morning", "2": "French", "...": "...", "40": "…"},
  "6": {"1": "…"}
}
```

外层 key = Test 号，内层 key = 题号（字符串），value = 答案原文（照抄总表，含备选写法）。
