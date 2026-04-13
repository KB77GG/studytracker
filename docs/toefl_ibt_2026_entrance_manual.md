# 新版 TOEFL iBT 入学诊断说明

本说明对应项目中的试卷 `新版 TOEFL iBT 入学诊断（2026 对应版）`。

## 对齐范围

- 以 ETS `Practice Test 5` 为题源。
- 对齐 `2026-01-21` 起生效的新版 TOEFL iBT 结构。
- 系统内落地了 `Reading / Listening / Writing`。
- `Speaking` 由于当前前台未接入录音作答，保留为教师面试或线下口语测试，后台继续录入 `speaking_score` 与 `speaking_comment`。

## 当前试卷结构

- Reading 1: Complete the Words，10 题
- Reading 2: Read in Daily Life（Email），2 题
- Reading 3: Read in Daily Life（Notice），3 题
- Reading 4: Read an Academic Passage，5 题
- Listening 1: Listen and Choose a Response，8 题
- Listening 2: Short Conversation，2 题
- Listening 3: Conversation，2 题
- Listening 4: Announcement，2 题
- Listening 5: Academic Talk，4 题
- Writing 1: Build a Sentence，10 题
- Writing 2: Write an Email，1 题
- Writing 3: Academic Discussion，1 题

## 媒体文件

脚本 `scripts/seed_toefl_2026_entrance_diagnostic.py` 会把需要的媒体整理到 `uploads/entrance/audio/`。

主要听力文件：

- `toefl_2026_pt5_listening_choose_response_m1.mp3`
- `toefl_2026_pt5_listening_conversation_9_10.mp3`
- `toefl_2026_pt5_listening_conversation_11_12.mp3`
- `toefl_2026_pt5_listening_announcement_13_14.mp3`
- `toefl_2026_pt5_listening_academic_talk_15_18.mp3`

已同步的口语文件：

- `toefl_2026_pt5_speaking_repeat_directions.ogg`
- `toefl_2026_pt5_speaking_repeat_1.ogg` 到 `toefl_2026_pt5_speaking_repeat_7.ogg`
- `toefl_2026_pt5_speaking_interview_directions.ogg`
- `toefl_2026_pt5_speaking_interview_1.mp4` 到 `toefl_2026_pt5_speaking_interview_4.mp4`

## 口语执行稿

### Listen and Repeat

建议先播放 directions，再依次播放 7 个句子，学生每句重复一次。

句子内容：

1. Here is how to start and adjust the treadmill.
2. There are many benches in the weightlifting area.
3. We do encourage the use of yoga mats for stretching out.
4. The rowing machine is excellent for a full-body workout.
5. We have plenty of exercise bikes for cardio training.
6. Please use the wipes provided at each station for cleaning equipment after use.
7. If you want to see great results quickly, consider joining our daily fitness classes.

### Take an Interview

建议先播放 directions，再逐题播放 interview 视频或由老师直接朗读。

题目内容：

1. From what you've seen, what kinds of careers do people around you tend to pursue?
2. When choosing a career, is job satisfaction your first priority, or do you focus more on salary? Why?
3. What are your thoughts on people changing careers multiple times throughout their lives?
4. Do you think artificial intelligence will continue changing jobs in your chosen field? Why or why not?

## 评分建议

- 写作评分参考桌面资料中的 `评分标准/writing-rubrics.pdf`。
- 口语评分参考桌面资料中的 `评分标准/speaking-rubrics.pdf`。
- 口语部分建议在教师后台统一填写：
- `speaking_score`
- `speaking_comment`
- `overall_level`
- `overall_comment`

## 使用方式

1. 运行 `python scripts/seed_toefl_2026_entrance_diagnostic.py`
2. 在入学测试后台选择新试卷并生成邀请链接
3. 学生在线完成 Reading / Listening / Writing
4. 老师补充口语测试并在批改页录入结果
