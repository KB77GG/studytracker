"""Reading Study grammar-term glossary and role normalization.

Faithful Python port of the ``CONCEPTS`` / ``FLAVORS`` / ``EXACT`` /
``resolveRole()`` logic that lives inside the ``<script>`` of
``data/reading_study/browse.html`` (the accepted interactive prototype).

The offline generator emits free-form snake_case ``structure[].role`` values
(~1449 distinct). At import time we normalize each into a closed vocabulary of
35 grammar concepts plus display labels, so the runtime front-end never needs a
role parser. The explanatory copy is preserved verbatim from the prototype.

Pure Python, no Flask dependency, unit-testable in isolation.
"""

from __future__ import annotations

import re

# 四大词性阵营 / 结构标记 的中文名（对应 browse.html 的 CAMP_NAMES）
CAMP_NAMES = {
    "noun": "名词阵营",
    "verb": "动词阵营",
    "adj": "形容词阵营",
    "adv": "副词阵营",
    "structure": "结构标记",
}

# 35 个封闭概念词表。每个值含 en/zh/camp/desc/ex，讲解文案逐字来自 browse.html。
CONCEPTS: dict[str, dict] = {
    "subject": {
        "en": "Subject",
        "zh": "主语",
        "camp": "noun",
        "desc": "句子的主角：谓语动作由它发出（被动句里则是动作的承受者）。名词阵营的成员都能当主语——名词、代词、动名词、名词性从句。读长难句先找到主语和谓语，主干就出来了。",
        "ex": "The government should take measures. → The government 是主语",
    },
    "verb_phrase": {
        "en": "Verb",
        "zh": "谓语",
        "camp": "verb",
        "desc": "句子的发动机。一个英语句子有且只能有一个动词单位（may have been done 这样的复合谓语也只算一个）。多出来的动词必须进从句、或者变形成非谓语——英语一半的语法都是这条规则推导出来的。",
        "ex": "She has finished the report. → has finished 是一个动词单位",
    },
    "object": {
        "en": "Object",
        "zh": "宾语",
        "camp": "noun",
        "desc": "动作的对象，跟在及物动词后面。名词能干的活它都能干，所以名词性从句、动名词也能当宾语。",
        "ex": "I read the book. → the book 是宾语",
    },
    "predicative": {
        "en": "Predicative",
        "zh": "表语",
        "camp": "noun",
        "desc": "跟在系动词（be / seem / become…）后面，说明主语「是什么、怎么样」，构成五大句型里的「主系表」。名词阵营和形容词阵营的成员都能担任。",
        "ex": "The result is surprising. → surprising 是表语",
    },
    "object_complement": {
        "en": "Object Complement",
        "zh": "宾语补足语",
        "camp": "structure",
        "desc": "补充说明宾语的状态或身份，和宾语一起构成「主谓宾宾补」句型。没有它句子意思不完整。",
        "ex": "They painted the wall white. → white 补充说明 the wall",
    },
    "complement": {
        "en": "Complement",
        "zh": "补语",
        "camp": "structure",
        "desc": "补足主语或宾语意思的成分。「主系表」和「主谓宾宾补」两种句型都靠它撑住——去掉补语，句子就说不完整了。",
        "ex": "The news made him happy. → happy 是补语",
    },
    "main_clause": {
        "en": "Main Clause",
        "zh": "主句",
        "camp": "structure",
        "desc": "句子的主干骨架，一定是五种基本句型之一：主谓 / 主谓宾 / 主谓双宾 / 主谓宾宾补 / 主系表。其余成分都是挂在它上面的修饰和补充。先锁定主句，长难句就解决了一半。",
        "ex": "Although it rained, we went out. → we went out 是主句",
    },
    "coordinate_clause": {
        "en": "Coordinate Clause",
        "zh": "并列分句",
        "camp": "structure",
        "desc": "用 and / but / or / while 等连接的「平级」句子——谁也不修饰谁，各自拥有自己的动词单位。这不违反「一句一动词」：并列相当于两个句子拼在一起。",
        "ex": "He came, and she left. → 两个平级分句",
    },
    "relative_clause": {
        "en": "Relative Clause",
        "zh": "定语从句",
        "camp": "adj",
        "desc": "整个从句当一个「大形容词」用，专门修饰它前面的名词（先行词）。为什么挂在名词后面？因为它比单个形容词长——「前短后长」：a beautiful girl 前置，a girl who is beautiful 后置，是同一个修饰关系。从句里有自己的动词，所以多出来的动作才要装进从句。",
        "ex": "the estimate that… / a girl who is beautiful → 从句修饰前面的名词",
    },
    "noun_clause": {
        "en": "Noun Clause",
        "zh": "名词性从句",
        "camp": "noun",
        "desc": "整个从句当一个「大名词」用——名词能干的活（主语、宾语、表语、同位语）它都能干。为什么要用从句？因为一句话只能有一个谓语动词，想再表达一个带动词的意思，就得给它单开一个从句、让它有自己的动词。",
        "ex": "I believe that he is right. → that 从句当宾语",
    },
    "adverbial_clause": {
        "en": "Adverbial Clause",
        "zh": "状语从句",
        "camp": "adv",
        "desc": "整个从句当一个「大副词」用，给主句交代时间、原因、条件、让步、目的等背景。副词阵营修饰除名词以外的一切，所以它的位置很灵活，句首句尾都常见。",
        "ex": "Although it rained, we went out. → 让步状语从句",
    },
    "prepositional_phrase": {
        "en": "Prepositional Phrase",
        "zh": "介词短语",
        "camp": "adv",
        "desc": "介词＋名词组成的小团队，是「两栖选手」：修饰名词时在形容词阵营（the book on the desk），修饰动词或整句时在副词阵营（He works in the morning）。它作定语时一律放在名词后面——因为比单个词长，前短后长。",
        "ex": "the rate of loss of rainforests → of… 修饰前面的名词",
    },
    "participial_phrase": {
        "en": "Participial Phrase",
        "zh": "分词短语",
        "camp": "adj",
        "desc": "动词的「变形」。一句话只能有一个谓语动词，多出来的动词就变形成分词，不再当谓语：-ing 表主动/进行，-ed 表被动/完成。它通常去形容词阵营修饰名词（作定语时后置，前短后长），或去副词阵营交代背景。",
        "ex": "the results published last year → published… 修饰 results",
    },
    "infinitive_phrase": {
        "en": "Infinitive",
        "zh": "不定式",
        "camp": "structure",
        "desc": "to＋动词原形，也是动词的「变形」（一句一动词的结果）。它是全能选手，三个阵营都能打工：当名词（To learn is fun）、当形容词修饰名词（a chance to win）、当副词表目的（He left early to catch the train）。",
        "ex": "measures to reduce pollution → to reduce… 修饰 measures",
    },
    "gerund_phrase": {
        "en": "Gerund",
        "zh": "动名词",
        "camp": "noun",
        "desc": "动词加 -ing 后当名词用，名词阵营成员。想让一个「动作」当主语或宾语时，就把动词变形成动名词——这也是「一句一动词」规则的产物。",
        "ex": "Reading improves vocabulary. → Reading 作主语",
    },
    "non_finite_clause": {
        "en": "Non-finite",
        "zh": "非谓语结构",
        "camp": "structure",
        "desc": "「一句一动词」的直接结果：多出来的动词必须变形上岗——to do（不定式）、doing（现在分词/动名词）、done（过去分词）。变形后它不再是谓语，而是去名词、形容词、副词三个阵营干活。",
        "ex": "people's ability to reason wisely → to reason 是非谓语",
    },
    "apposition": {
        "en": "Apposition",
        "zh": "同位语",
        "camp": "noun",
        "desc": "紧跟在一个名词后面、把它再解释一遍的成分——两者说的是同一个东西。常用逗号或破折号隔开。读句子时可以把它当作「补充说明卡片」。",
        "ex": "Mr. Li, our teacher, … → our teacher ＝ Mr. Li",
    },
    "parenthesis": {
        "en": "Parenthesis",
        "zh": "插入语",
        "camp": "structure",
        "desc": "临时插进句子里的补充说明，常用逗号、破折号或括号隔开。读长难句的技巧：先跳过插入语、看完主干再回来读它。",
        "ex": "The plan, however, failed. → however 是插入语",
    },
    "adverbial": {
        "en": "Adverbial",
        "zh": "状语",
        "camp": "adv",
        "desc": "副词阵营的主力：给动作或整句补充时间、地点、方式、程度等信息。副词、介词短语、分词短语、从句都能干这活。副词阵营修饰除名词以外的一切。",
        "ex": "He works in the morning. → in the morning 是时间状语",
    },
    "linking_verb": {
        "en": "Linking Verb",
        "zh": "系动词",
        "camp": "verb",
        "desc": "be / seem / become / remain 这类「连接型」动词：自己没多少动作含义，负责把主语和表语连起来，构成「主系表」句型。它也是一个完整的动词单位。",
        "ex": "The result is surprising. → is 是系动词",
    },
    "passive_predicate": {
        "en": "Passive Verb",
        "zh": "被动谓语",
        "camp": "verb",
        "desc": "be＋过去分词。主语不是动作的发出者，而是承受者。学术文章特别爱用被动——隐去「谁做的」，突出「发生了什么」。它仍然只是一个动词单位。",
        "ex": "The data were collected in 2020. → were collected 是被动谓语",
    },
    "existential_clause": {
        "en": "Existential",
        "zh": "存现句 There be",
        "camp": "structure",
        "desc": "There be 句型，表示「某处存在某物」。there 只是占位子，真正的主语在 be 后面——这也是「前短后长」：把较长的真主语挪到后面。",
        "ex": "There are three reasons. → 真主语是 three reasons",
    },
    "reporting_clause": {
        "en": "Reporting Clause",
        "zh": "引述句",
        "camp": "structure",
        "desc": "「某人说 / 研究表明」这类引出观点的小句：says Professor Li、the study suggests。先认出它，剩下的部分就是被引用的内容本身。",
        "ex": "…, says Associate Professor Grossmann. → 引述句",
    },
    "direct_speech": {
        "en": "Direct Speech",
        "zh": "直接引语",
        "camp": "structure",
        "desc": "引号里原封不动引用的话，是被引述的内容。它内部自成一个完整句子，按正常句子拆解即可。",
        "ex": "'It appears that…,' says the professor.",
    },
    "attribution": {
        "en": "Attribution",
        "zh": "引述来源",
        "camp": "structure",
        "desc": "标明前述观点或直接引语来自谁。它可以是引语后的说话人姓名，也可以是 according to… / as…remarked 这类来源说明；它不属于被引内容本身的句子主干。",
        "ex": "'I have also bought…' — Doreen Soko → Doreen Soko 是引语署名",
    },
    "discourse_marker": {
        "en": "Discourse Marker",
        "zh": "连接副词",
        "camp": "adv",
        "desc": "however / therefore / moreover 这类词，负责句子之间的逻辑衔接（转折、因果、递进）。注意：它是副词、不是连词，不能直接把两个句子连成一句——所以常见「分号或句号＋however＋逗号」。",
        "ex": "The plan failed. However, we learned a lot.",
    },
    "conjunction": {
        "en": "Conjunction",
        "zh": "连接词",
        "camp": "structure",
        "desc": "and / but / because / although 等，把词、短语或句子连接起来的「胶水」。并列连词连接平级成分；从属连词引出从句。",
        "ex": "because it rained → because 引出原因状语从句",
    },
    "formal_subject": {
        "en": "Formal Subject",
        "zh": "形式主语 it",
        "camp": "structure",
        "desc": "it 占在主语位置，真正的主语（不定式或从句）太长，按「前短后长」挪到了句尾。翻译时要找到真主语再理解。",
        "ex": "It is important to sleep well. → 真主语是 to sleep well",
    },
    "absolute": {
        "en": "Absolute Construction",
        "zh": "独立主格",
        "camp": "adv",
        "desc": "「名词＋分词/介词短语」独立地给整句补充背景信息，常带 with。它有自己的逻辑主语，但没有真正的谓语动词——所以不算独立句子，整体在副词阵营干活。",
        "ex": "With prices rising, people spend less.",
    },
    "comparative": {
        "en": "Comparative",
        "zh": "比较结构",
        "camp": "structure",
        "desc": "than / as…as 引导的比较，说明两者的程度差异。比较对象后面常有省略，把省略的部分补全，句子就好懂了。",
        "ex": "more powerful than previously imagined → than 后省略了 it was",
    },
    "cleft": {
        "en": "Cleft Sentence",
        "zh": "强调结构",
        "camp": "structure",
        "desc": "It is … that … 把要强调的成分提到前面、其余后置——还是「前短后长」在不同场景下的应用。去掉 It is 和 that，句子照样成立。",
        "ex": "It is the context that matters. → 强调 the context",
    },
    "inversion": {
        "en": "Inversion",
        "zh": "倒装",
        "camp": "structure",
        "desc": "把谓语（或助动词）提到主语前面。常见于否定词开头（Never have I…）、only 开头等。目的通常是强调，或让句子头轻脚重更平衡。",
        "ex": "Nowhere is this more evident than… → 否定词开头引起倒装",
    },
    "adjective_phrase": {
        "en": "Adjective Phrase",
        "zh": "形容词短语",
        "camp": "adj",
        "desc": "以形容词为核心的短语，形容词阵营成员：修饰名词，或跟在系动词后当表语。带补充成分变长时，作定语要后置——前短后长。",
        "ex": "a task difficult to finish → difficult to finish 后置修饰 task",
    },
    "noun_phrase": {
        "en": "Noun Phrase",
        "zh": "名词短语",
        "camp": "noun",
        "desc": "以名词为核心的一组词，名词阵营成员，句子里当主语、宾语、表语等。中心名词前后挂着的都是修饰它的成分。",
        "ex": "the alarming rate of loss → 中心词是 rate",
    },
    "generic_phrase": {
        "en": "Phrase",
        "zh": "短语",
        "camp": "structure",
        "desc": "以某类词为核心的一组词，整体在句中担任一个成分。判断它的方法：看它在句子里「干什么活」——当名词用、修饰名词、还是修饰动词/整句。",
        "ex": None,
    },
    "heading": {
        "en": "Heading",
        "zh": "小标题",
        "camp": "structure",
        "desc": "原文排版里的小节标题，不是句子成分，起分段导航作用。",
        "ex": None,
    },
}

# 语义前缀（时间/目的/条件…），给状语(从句)拼出更精确的中文/英文标签。
FLAVORS = {
    "time": "时间",
    "place": "地点",
    "reason": "原因",
    "cause": "原因",
    "purpose": "目的",
    "result": "结果",
    "condition": "条件",
    "conditional": "条件",
    "concessive": "让步",
    "concession": "让步",
    "contrast": "对比",
    "manner": "方式",
    "means": "方式",
    "degree": "程度",
    "comparative": "比较",
    "comparison": "比较",
    "frequency": "频率",
    "duration": "持续",
    "source": "来源",
    "accompaniment": "伴随",
    "explanatory": "解释说明",
    "example": "举例",
    "sentence": "句子",
}

# 精确映射表：原始 role → 概念 id，或 [概念 id, 中文覆盖, 英文覆盖]。
EXACT: dict[str, object] = {
    "subject": "subject",
    "compound_subject": "subject",
    "gerund_subject": "gerund_phrase",
    "verb": "verb_phrase",
    "verb_phrase": "verb_phrase",
    "predicate": "verb_phrase",
    "main_predicate": "verb_phrase",
    "coordinated_predicate": "verb_phrase",
    "coordinate_predicate": "verb_phrase",
    "coordinated_verb_phrase": "verb_phrase",
    "linking_predicate": "linking_verb",
    "linking_verb": "linking_verb",
    "passive_predicate": "passive_predicate",
    "passive_verb_phrase": "passive_predicate",
    "passive_verb": "passive_predicate",
    "passive_main_clause": "main_clause",
    "object": "object",
    "predicate_object": "object",
    "predicative": "predicative",
    "subject_complement": "predicative",
    "object_complement": "object_complement",
    "complement": "complement",
    "verb_complement": "complement",
    "infinitive_complement": "infinitive_phrase",
    "prepositional_complement": "prepositional_phrase",
    "main_clause": "main_clause",
    "coordinated_clause": "coordinate_clause",
    "coordinate_clause": "coordinate_clause",
    "relative_clause": "relative_clause",
    "attributive_clause": "relative_clause",
    "nonrestrictive_relative_clause": "relative_clause",
    "noun_clause": "noun_clause",
    "content_clause": "noun_clause",
    "that_clause": "noun_clause",
    "embedded_question": "noun_clause",
    "subject_clause": ["noun_clause", "主语从句", "Subject Clause"],
    "object_clause": ["noun_clause", "宾语从句", "Object Clause"],
    "predicative_clause": ["noun_clause", "表语从句", "Predicative Clause"],
    "appositive_clause": ["noun_clause", "同位语从句", "Appositive Clause"],
    "adverbial_clause": "adverbial_clause",
    "apposition": "apposition",
    "appositive": "apposition",
    "parenthesis": "parenthesis",
    "parenthetical_clause": "parenthesis",
    "non_finite_clause": "non_finite_clause",
    "participial_phrase": "participial_phrase",
    "past_participial_phrase": "participial_phrase",
    "past_participle_modifier": "participial_phrase",
    "present_participle_modifier": "participial_phrase",
    "infinitive_phrase": "infinitive_phrase",
    "gerund_phrase": "gerund_phrase",
    "prepositional_phrase": "prepositional_phrase",
    "adverbial": "adverbial",
    "adverbial_phrase": "adverbial",
    "adverb": "adverbial",
    "reporting_clause": "reporting_clause",
    "quoted_clause": "direct_speech",
    "direct_speech": "direct_speech",
    "speaker_attribution": ["attribution", "引语署名", "Speaker Attribution"],
    "attribution_phrase": ["attribution", "来源短语", "Attribution Phrase"],
    "attribution_adverbial": ["attribution", "来源状语", "Attribution Adverbial"],
    "attribution_clause": ["attribution", "来源说明从句", "Attribution Clause"],
    "discourse_marker": "discourse_marker",
    "conjunctive_adverb": "discourse_marker",
    "conjunction": "conjunction",
    "existential_clause": "existential_clause",
    "formal_subject": "formal_subject",
    "with_absolute_construction": "absolute",
    "comparative_clause": "comparative",
    "comparative_phrase": "comparative",
    "adjective_phrase": "adjective_phrase",
    "noun_phrase": "noun_phrase",
    "heading": "heading",
    "explanatory_clause": ["adverbial_clause", "解释说明分句", "Explanatory Clause"],
    "example_phrase": ["adverbial", "举例短语", "Example Phrase"],
}

# 兜底：无法归入封闭概念词表的 role（browse.html resolveRole 的 base=null 分支）。
_FALLBACK = {
    "en": "Grammatical Role",
    "zh": "语法成分",
    "camp": "structure",
    "desc": "这是一个语法功能标注。理解它的方法：别管名字，看它在句子里「干什么活」——当名词用（名词阵营）、修饰名词（形容词阵营）、还是修饰动词或整句（副词阵营）。",
    "ex": None,
}
_FALLBACK_CONCEPT = "unknown"

_resolve_cache: dict[str, dict] = {}


def humanize(role: str) -> str:
    """snake_case → Title Case（对应 browse.html humanize）。"""
    return " ".join(word[:1].upper() + word[1:] for word in str(role or "").split("_"))


def _match(pattern: str, value: str) -> bool:
    return re.search(pattern, value) is not None


def resolve_role(role: str) -> dict:
    """归一化一个原始 role，返回 ``{concept, zh, en, camp}``。

    忠实移植 browse.html 的 resolveRole()：先查 EXACT，再走后缀/词干规则，
    带 flavor 的状语(从句)拼出精确标签，最后兜底。concept 一定是
    ``glossary_payload()['concepts']`` 里的一个 key（35 概念之一或 unknown）。
    """
    role = str(role or "")
    if role in _resolve_cache:
        return _resolve_cache[role]

    key = None
    zh_override = None
    en_override = None
    flavor = None

    exact = EXACT.get(role)
    if isinstance(exact, list):
        key, zh_override, en_override = exact[0], exact[1], exact[2]
    elif exact:
        key = exact

    if not key:
        r = role
        prefix = r.split("_")[0]
        if _match("heading", r):
            key = "heading"
        elif _match("attribution", r):
            key = "attribution"
        elif _match(r"_clause$|^clause", r):
            if _match("relative|attributive|nonrestrictive", r):
                key = "relative_clause"
            elif _match("subject|object|predicative|appositive|content|that|noun|embedded|wh_", r):
                key = "noun_clause"
            elif _match("report|quot|speech", r):
                key = "reporting_clause"
            elif _match("existential", r):
                key = "existential_clause"
            elif _match("coordinat|parallel|compound", r):
                key = "coordinate_clause"
            elif _match("main", r):
                key = "main_clause"
            elif _match("cleft|emphat", r):
                key = "cleft"
            elif _match("invert", r):
                key = "inversion"
            else:
                key = "adverbial_clause"
                if prefix in FLAVORS:
                    flavor = prefix
        elif _match("participial|participle", r):
            key = "participial_phrase"
        elif _match("infinitive", r):
            key = "infinitive_phrase"
        elif _match("gerund", r):
            key = "gerund_phrase"
        elif _match("non_?finite", r):
            key = "non_finite_clause"
        elif _match("apposit", r):
            key = "apposition"
        elif _match("parenthe", r):
            key = "parenthesis"
        elif _match(r"adverbial|_adverb$|^adverb$", r):
            key = "adverbial"
            if prefix in FLAVORS:
                flavor = prefix
        elif _match("subject_complement|predicative", r):
            key = "predicative"
        elif _match("object_complement", r):
            key = "object_complement"
        elif _match("complement", r):
            key = "complement"
        elif _match("formal_subject|dummy", r):
            key = "formal_subject"
        elif _match("linking", r):
            key = "linking_verb"
        elif _match("passive", r):
            key = "passive_predicate"
        elif _match("subject", r):
            key = "subject"
        elif _match("object", r):
            key = "object"
        elif _match("predicate|verb", r):
            key = "verb_phrase"
        elif _match("preposition", r):
            key = "prepositional_phrase"
        elif _match("conjunctive|discourse|marker|connector", r):
            key = "discourse_marker"
        elif _match("conjunction", r):
            key = "conjunction"
        elif _match("speech|quote", r):
            key = "direct_speech"
        elif _match("cleft|emphat", r):
            key = "cleft"
        elif _match("invert|inversion", r):
            key = "inversion"
        elif _match("absolute", r):
            key = "absolute"
        elif _match("comparat|comparison", r):
            key = "comparative"
        elif _match("adjectiv", r):
            key = "adjective_phrase"
        elif _match("noun", r):
            key = "noun_phrase"
        elif _match("coordinat|parallel", r):
            key = "coordinate_clause"
        elif _match("phrase", r):
            key = "generic_phrase"

    base = CONCEPTS.get(key)
    if not base:
        out = {
            "concept": _FALLBACK_CONCEPT,
            "en": humanize(role) or _FALLBACK["en"],
            "zh": _FALLBACK["zh"],
            "camp": _FALLBACK["camp"],
        }
    else:
        zh = zh_override or base["zh"]
        en = en_override or base["en"]
        if flavor and flavor in FLAVORS:
            if key == "adverbial_clause":
                zh = FLAVORS[flavor] + "状语从句"
                en = humanize(flavor) + " Clause"
            elif key == "adverbial":
                zh = FLAVORS[flavor] + "状语"
                en = humanize(flavor) + " Adverbial"
        out = {"concept": key, "en": en, "zh": zh, "camp": base["camp"]}

    _resolve_cache[role] = out
    return out


def glossary_payload() -> dict:
    """给前端的完整词典：概念讲解（含兜底）+ 阵营中文名。

    ``concepts`` 的每个 key 都可能被 ``resolve_role()`` 作为 ``concept`` 返回，
    保证前端点任意语法标签都能查到讲解，不会「点了没反应」。
    """
    concepts = {
        concept_id: {
            "en": data["en"],
            "zh": data["zh"],
            "camp": data["camp"],
            "desc": data["desc"],
            "ex": data["ex"],
        }
        for concept_id, data in CONCEPTS.items()
    }
    concepts[_FALLBACK_CONCEPT] = {
        "en": _FALLBACK["en"],
        "zh": _FALLBACK["zh"],
        "camp": _FALLBACK["camp"],
        "desc": _FALLBACK["desc"],
        "ex": _FALLBACK["ex"],
    }
    return {"camps": dict(CAMP_NAMES), "concepts": concepts}
