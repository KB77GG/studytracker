# Reading Study v1 生成标准

每个 Passage 生成一个 JSON 文件：

`data/reading_study/{passage_id}.json`

金标准参照：

- `data/reading_study/ielts16_test2_p1.json`
- `data/reading_study/ielts16_test2_p2.json`
- `data/reading_study/ielts16_test2_p3.json`

## 顶层格式

```json
{
  "schema_version": 1,
  "generation_standard": "reading_study_v1",
  "source_kind": "reading_test",
  "test_id": "ielts16_test2_reading",
  "passage_id": "ielts16_test2_p1",
  "passage_title": "The White Horse of Uffington",
  "difficulty": "simple",
  "sentences": []
}
```

- `source_kind` 只能是 `reading_test` 或 `reading_jijing`，由源目录决定。
- `difficulty` 按 Passage 1/2/3 分别使用 `simple` / `medium` / `complex`。

## 句子格式

每句固定包含：

```json
{
  "id": "A-01",
  "paragraph_label": "A",
  "sentence_index": 1,
  "sentence": "完整英文原句。",
  "translation": "自然中文翻译。",
  "structure": [
    {"text": "原句中的连续片段", "role": "subject", "level": 1}
  ],
  "difficult_points": ["难点一。", "难点二。"],
  "expressions": [
    {"text": "academic expression", "meaning_zh": "中文含义"}
  ]
}
```

## 内容要求

1. 按段落顺序拆句；`sentence` 必须逐字保留原文，不能修改标点、引号、大小写或脚注标记。
2. 同一段全部句子以单个空格重新拼接后，必须与源段落一致。
3. `translation` 使用自然中文，不逐词硬译，不增加原文没有的结论。
4. `structure` 是语法拆解，不是普通断句：
   - 每个 `text` 必须是原句中的连续原文片段，不使用 `...`。
   - `role` 使用 snake_case 英文语法标签。
   - `level` 从 1 开始；主干为 1，从句内部依次增加。
   - 介词短语不能标成 `adverbial_clause`；连接副词不能标成从句。
5. `difficult_points` 固定 2–4 条，每条一句中文，只解释真正影响理解的指代、修饰、从句、时态、语态、倒装、省略或非谓语。
6. `expressions` 为 0–4 条：
   - 只选固定搭配、高频学术表达、写作可迁移表达或有价值的动词。
   - 不收普通名词、临时性的原文片段或缺乏迁移价值的组合。
   - `text` 保留适合积累的词形；`meaning_zh` 必须符合当前语境。
7. JSON 使用 UTF-8，不能包含 Markdown 或注释。

## 验证

每完成一个 Passage 后运行：

```bash
.venv/bin/python scripts/validate_reading_study.py
```

验证器必须通过后才算完成。
