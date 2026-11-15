# 实样探针适配说明

原探针调用第一版的私有诊断辅助 `_Sentences` / `corrected_values` / `_values`，新代码重写后该接口已不存在，因此原样执行在诊断阶段报 `AttributeError`，尚未完成验收。此问题属于探针的内部调试耦合。

本轮副本只删除下面 35 行私有诊断代码。所有模型结果归一化、输入/源码保护、验收检查和预期不变；从 `checks = []` 开始至文件末尾逐字相同，SHA 见 [replay-review.json](replay-review.json)。L9 的新诊断另存本机私有目录，只共享布尔结论。

205 项总数并非增加或放宽验收：原脚本对保留的建议检查一次，对新增删除检查两次（标记、评语保持）。L9 正确删除后，原 204 项动态增加为 205 项。

```diff
--- original/replay_probe.py
+++ adapted/replay_probe.py
@@ -92,41 +92,7 @@
                 == digest({"submission": submission, "raw": raw}),
             }
         )
-        if (
-            sample["id"] == "official-1B-A#r2"
-            and (args.source / "tools/ielts_writing_ai/conflicts.py").is_file()
-        ):
-            from tools.ielts_writing_ai import conflicts, figures
-
-            task_raw = raw["criteria"]["task"]["issues"][1]
-            task_normalized = normalized["criteria"][0]["issues"][1]
-            language = normalized["criteria"][3]["issues"][1]
-            sentences = conflicts._Sentences(submission["essay_text"])
-            raw_values = conflicts.corrected_values(dict(task_raw, quote_found=True))
-            diagnostics.append(
-                {
-                    "id": "L9",
-                    "sample_id": sample["id"],
-                    "task_raw_field": "criteria.task.issues[1]",
-                    "language_field": "criteria.grammar.issues[1]",
-                    "task_raw": task_raw,
-                    "task_normalized": task_normalized,
-                    "language_normalized": language,
-                    "unsourced_in_task_suggestion": figures.for_submission(
-                        submission, chart_checked=True
-                    ).unsourced(task_raw["suggestion"]),
-                    "raw_corrected_values": sorted(raw_values),
-                    "normalized_corrected_values": sorted(
-                        conflicts.corrected_values(task_normalized)
-                    ),
-                    "retained_corrected_values": sorted(
-                        conflicts._values(language["suggestion"]) & raw_values
-                    ),
-                    "same_sentence": bool(
-                        sentences.of(task_raw["quote"]) & sentences.of(language["quote"])
-                    ),
-                }
-            )
+        # Legacy private diagnostics used removed helpers; acceptance checks unchanged.
     write_json(
         args.worker_out,
         {
```
