#!/usr/bin/env python3
"""Seed 8 tiered TOEFL entrance test papers (reading + writing) by extracting
real exam passages from post-March 2026 test materials.

Idempotent: skipped if (title, exam_type) already exists.

Tiers (TOEFL total score, 0-120):
  - toefl_60_80      入门 60-80     (2 papers, A/B)
  - toefl_80_95      中阶 80-95     (2 papers, A/B)
  - toefl_95_105     高阶 95-105    (2 papers, A/B)
  - toefl_105_plus   冲刺 105+      (2 papers, A/B)

Source: real TOEFL reading passages from 2026/3-4 exams (3.10/3.18/3.27/3.30/
4.1/4.5/4.6/4.8). Each paper = 1 reading passage (~250-300 words) with 3-5
multi-choice questions + 1 AI-authored Academic Discussion writing prompt.
~20-25 minutes per paper.

Note: questions of types "sentence insertion (4-location)" and "sentence
pick" from real exams are skipped since our entrance system supports only
single_choice / short_answer / essay.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import (
    db,
    User,
    EntranceTestPaper,
    EntranceTestSection,
    EntranceTestQuestion,
)


def _opts(pairs):
    return json.dumps(
        [{"key": k, "text": t} for k, t in pairs], ensure_ascii=False
    )


def _mcq(seq, stem, options, answer, analysis=None):
    return {
        "sequence": seq,
        "question_type": "single_choice",
        "stem": stem,
        "options_json": _opts(options),
        "correct_answer": answer,
        "points": 1,
        "reference_answer": analysis,
    }


# ---------------------------------------------------------------------------
# Reading passages + questions (all extracted from real exam materials)
# ---------------------------------------------------------------------------

# 4.6 入门 A — Video Evidence in U.S. Courts
PASSAGE_4_6 = (
    "In the United States, as in some other countries, video evidence has "
    "become integral to the criminal justice system as technological advances "
    "have made cameras nearly ubiquitous. Police officers often wear body "
    "cameras, security cameras monitor public areas, and nearly everyone "
    "carries a smartphone capable of recording high-quality videos. While "
    "such recordings are widely seen as reliable evidentiary tools, they have "
    "certain limitations.\n\n"
    "For example, videos are usually taken from a single vantage point, "
    "potentially giving viewers a misleading impression of events. A single "
    "camera angle might fail to capture what occurs just outside the frame, "
    "leading observers to misinterpret what they see. Additionally, video "
    "footage has no way of conveying interpersonal and emotional context: A "
    "person's actions might appear antagonistic even if the person was acting "
    "in self-defense.\n\n"
    "Despite these limitations, legal experts emphasize that video evidence "
    "plays a significant role in courtrooms. Jurors (people chosen to "
    "consider evidence and decide a case) might dismiss eyewitness "
    "testimonies as unreliable or perceive oral accounts as inconsistent, "
    "while videos show events more directly. When multiple recordings are "
    "available from different angles, an even more reliable sense of an "
    "incident can emerge. Nevertheless, courts often remind jurors to "
    "evaluate video evidence cautiously."
)
QUESTIONS_4_6 = [
    _mcq(1,
        "What is the relationship between the first sentence and the second sentence of the passage?",
        [
            ("A", "The first sentence makes a generalization, and the second sentence introduces exceptions to the generalization."),
            ("B", "The first sentence presents one view of a subject, and the second sentence presents a contrasting view."),
            ("C", "The first sentence makes a claim, and the second sentence provides examples to illustrate that claim."),
            ("D", "The first sentence introduces a question, and the second sentence offers possible answers to the question."),
        ],
        "C"),
    _mcq(2,
        "The passage suggests which of the following about viewers of videos?",
        [
            ("A", "They are more likely to trust the accuracy of a video recorded on a police officer's body camera than one taken with a smartphone."),
            ("B", "They may not find a video recording of an incident as revealing as an eyewitness account of the event."),
            ("C", "They may not see actions that are critical to understanding an incident because of the way the video is framed."),
            ("D", "They are likely to regard video recordings skeptically because they know that videos can be misleading."),
        ],
        "C"),
    _mcq(3,
        "What does the author point out when discussing \"context\"?",
        [
            ("A", "The setting in which a video is viewed may affect the way viewers perceive the recorded events."),
            ("B", "People may draw incorrect conclusions about others' motivations from what they observe in a video."),
            ("C", "Video recordings can be used either to defend an individual's actions or to depict the individual as an aggressor."),
            ("D", "The reliability of video recordings of events should be compared to the reliability of oral accounts of those events."),
        ],
        "B"),
    _mcq(4,
        "The passage indicates that \"legal experts\" hold which of the following views?",
        [
            ("A", "Jurors are likely to accept videos as objective depictions of events whereas they view witness testimony with skepticism."),
            ("B", "Recent improvements in technology have made it so easy to display video evidence to jurors that other kinds of evidence may be neglected."),
            ("C", "Video recordings should not be used as evidence in courtrooms unless multiple recordings taken from different vantage points can be shown."),
            ("D", "Courts should not undermine jurors' abilities by overemphasizing the possibility of misinterpreting videos."),
        ],
        "A"),
    _mcq(5,
        "The word \"cautiously\" in the passage is closest in meaning to",
        [("A", "reluctantly"), ("B", "carefully"), ("C", "decisively"), ("D", "confidently")],
        "B"),
]

# 3.30 入门 B — The Political Legacy of the Roman Empire
PASSAGE_3_30 = (
    "The fall of the Roman Empire reshaped the geopolitical landscape of "
    "Europe and the Mediterranean in profound ways. One widely accepted "
    "hypothesis is that the collapse of Roman administrative and military "
    "structures led to the fragmentation of centralized authority. Without "
    "Rome's unifying legal framework, power devolved to local warlords and "
    "tribal leaders, paving the way for feudalism and a mosaic of competing "
    "kingdoms. This decentralization fostered chronic instability, as seen "
    "in the frequent conflicts among the Franks, Visigoths, and Lombards.\n\n"
    "However, some scholars argue that this fragmentation was not purely "
    "detrimental. The absence of a dominant empire may have encouraged "
    "regional innovation and adaptability. For instance, the Carolingian "
    "Renaissance under Charlemagne suggests that localized rule could still "
    "produce cultural and intellectual flourishing. The emergence of monastic "
    "communities during this period also played a crucial role in preserving "
    "classical knowledge and fostering educational continuity across "
    "fragmented territories.\n\n"
    "Another compelling example is the Byzantine Empire, which retained "
    "Roman governance in the East and acted as a stabilizing force for "
    "centuries. Its survival challenges the notion that imperial collapse "
    "inevitably leads to disorder. While the fall of Rome dismantled a "
    "centralized system, it also opened space for diverse political "
    "experiments—some chaotic, and others surprisingly resilient."
)
QUESTIONS_3_30 = [
    _mcq(1,
        "The word \"fostered\" in the passage is closest in meaning to",
        [("A", "accepted"), ("B", "revealed"), ("C", "preceded"), ("D", "promoted")],
        "D"),
    _mcq(2,
        "Which of the following best describes the main purpose of paragraph 1?",
        [
            ("A", "To highlight the cultural achievements that followed the Roman Empire's collapse"),
            ("B", "To argue that the fall of Rome had minimal impact on European governance"),
            ("C", "To present a common explanation for the political fragmentation after Rome's fall"),
            ("D", "To contrast the Roman Empire's decline with the rise of local kingdoms"),
        ],
        "C"),
    _mcq(3,
        "Why does the author mention the Carolingian Renaissance?",
        [
            ("A", "To illustrate that cultural growth was still possible despite political fragmentation"),
            ("B", "To show how Charlemagne attempted to restore the Roman Empire's boundaries"),
            ("C", "To argue that feudalism was a direct result of the Roman Empire's policies"),
            ("D", "To emphasize the role of military conflicts in shaping post-Roman Europe"),
        ],
        "A"),
    _mcq(4,
        "The passage mentions each of the following as a consequence of the Roman Empire's collapse EXCEPT",
        [
            ("A", "the rise of feudalism and competing regional kingdoms"),
            ("B", "the expansion of the Byzantine Empire into Western Europe"),
            ("C", "the preservation of classical knowledge in monastic communities"),
            ("D", "the transfer of political authority to local leaders"),
        ],
        "B"),
]

# 4.5 中阶 A — Expert Systems
PASSAGE_4_5 = (
    "Expert systems are a branch of artificial intelligence designed to mimic "
    "the decision-making abilities of human experts. These systems use a "
    "knowledge base of specialized information and rules to solve specific "
    "problems. Their goal is to replicate the expertise and reasoning of "
    "professionals in fields like medicine and engineering.\n\n"
    "An early expert system is MYCIN, developed in the 1970s to diagnose "
    "bacterial infections and recommend antibiotics. MYCIN used rules "
    "provided by medical experts to analyze patient data, infer diagnoses, "
    "and suggest treatments. MYCIN often performed as well as human "
    "specialists; however, MYCIN's system needed constant updates, requiring "
    "extensive input from medical professionals.\n\n"
    "Despite their potential, expert systems have limitations; since they "
    "rely on static knowledge databases, they can become outdated without "
    "ongoing input from human experts. The process of updating the system "
    "can be labor-intensive. Advancements in machine learning and natural "
    "language processing could address these issues. By integrating these "
    "technologies, expert systems could learn from new data and adapt, "
    "improving accuracy and relevance. Researchers are optimistic that these "
    "advancements will transform expert systems, enabling them to tackle a "
    "wider range of challenges and operate more independently."
)
QUESTIONS_4_5 = [
    _mcq(1,
        "The word \"mimic\" in the passage is closest in meaning to",
        [("A", "replace"), ("B", "combine"), ("C", "imitate"), ("D", "challenge")],
        "C"),
    _mcq(2,
        "How did MYCIN diagnose bacterial infections?",
        [
            ("A", "It used a human specialist to evaluate patient data."),
            ("B", "It applied set rules to analyze patient data."),
            ("C", "It used data on infection rates to infer the probability of a particular type of bacteria."),
            ("D", "It relied on information provided directly by the patients."),
        ],
        "B"),
    _mcq(3,
        "What is a major limitation of current expert systems mentioned in the passage?",
        [
            ("A", "They are unable to process large datasets."),
            ("B", "They often provide incorrect results."),
            ("C", "They need frequent updating."),
            ("D", "They use databases that are always changing."),
        ],
        "C"),
    _mcq(4,
        "What can be inferred about the future of expert systems?",
        [
            ("A", "They will probably be limited to use in medical applications."),
            ("B", "They will one day be able to update themselves without human input."),
            ("C", "They will become less accurate as the amount of new data increases."),
            ("D", "They will soon be replaced by more relevant technologies."),
        ],
        "B"),
]

# 4.8 中阶 B — Cybernetic Prosthetics
PASSAGE_4_8 = (
    "Cybernetic prosthetics have revolutionized medical technology, offering "
    "hope to individuals who have lost limbs. Unlike traditional prosthetics, "
    "which are often cumbersome and limited in function, cybernetic versions "
    "are designed to integrate seamlessly with the human nervous system. "
    "This integration allows for more natural movement and even sensation. A "
    "key development in this field has been the use of myoelectric sensors, "
    "which detect electrical signals generated by muscle movements.\n\n"
    "One example is a cybernetic hand that can perform delicate tasks such "
    "as picking up small objects or typing. This is achieved through "
    "advanced algorithms that translate muscle signals into controlled "
    "movements. Researchers are also exploring haptic feedback, which would "
    "enable users to feel textures and temperatures through their prosthetic "
    "limbs. It involves integrating sensors and actuators that mimic the "
    "sensation of touch by stimulating the user's nerve endings or skin with "
    "electrical signals. This could significantly improve the quality of "
    "life for amputees.\n\n"
    "The high cost of these prosthetics makes them inaccessible to many. "
    "Additionally, the technology requires regular maintenance and updates, "
    "which can be a barrier. Current battery life is another limitation, as "
    "it restricts the user's ability to wear the prosthetic for extended "
    "periods. Researchers are continually working to make these devices more "
    "affordable and user-friendly."
)
QUESTIONS_4_8 = [
    _mcq(1,
        "The word \"seamlessly\" in the passage is closest in meaning to",
        [("A", "generally"), ("B", "smoothly"), ("C", "repeatedly"), ("D", "slowly")],
        "B"),
    _mcq(2,
        "What can be inferred about myoelectric sensors?",
        [
            ("A", "They function less effectively in traditional prosthetics."),
            ("B", "They rely less on electric signals than other types of sensors do."),
            ("C", "They allow for more natural movement in cybernetic prosthetics."),
            ("D", "They make cybernetic prosthetics somewhat cumbersome."),
        ],
        "C"),
    _mcq(3,
        "What does the passage indicate about cybernetic hands?",
        [
            ("A", "They are very similar in appearance to natural human limbs."),
            ("B", "They are currently limited in their range of motion."),
            ("C", "They rely on algorithms that turn muscle signals into movements."),
            ("D", "They can cause skin irritation if worn for extended periods."),
        ],
        "C"),
]

# 4.1 高阶 A — Understanding Ecological Systems Theory
PASSAGE_4_1 = (
    "Ecological Systems Theory, introduced by Urie Bronfenbrenner, "
    "revolutionized our perception of human psychological development. It "
    "posits that individuals are shaped by interactions among multiple "
    "overlapping environmental systems. This theory reshaped developmental "
    "research, offering a multi-faceted lens that surpasses earlier, linear "
    "models. By considering the dynamic interplay between a person and their "
    "environment, it highlights the multifactorial nature of psychological "
    "growth.\n\n"
    "The theory delineates several environmental layers, beginning with the "
    "microsystem, which refers to the institutions and groups that most "
    "directly impact the child's development, such as family and school. The "
    "mesosystem encompasses the relationships among the microsystems, such "
    "as the impact of a teacher's communication with parents on a child's "
    "education. Beyond these, the exosystem consists of indirect influences "
    "like a parent's workplace stress subtly affecting the home environment. "
    "The macrosystem, encompassing broader cultural and societal contexts, "
    "frames these interactions with underlying norms and policies.\n\n"
    "While Bronfenbrenner's model offers an intricate framework, it is not "
    "without critique. Some argue that the model underestimates the role of "
    "technology, which has created virtual microsystems that transcend "
    "geographical limits. Despite these critiques, the theory remains "
    "influential in fields ranging from education to public policy, "
    "prompting continuous exploration of its applications and adaptations."
)
QUESTIONS_4_1 = [
    _mcq(1,
        "The phrase \"subtly affecting\" in the passage is closest in meaning to",
        [
            ("A", "affecting in harmless but unpredictable ways"),
            ("B", "affecting in long-lasting ways"),
            ("C", "affecting in ways both positive and negative"),
            ("D", "affecting in small, barely noticeable ways"),
        ],
        "D"),
    _mcq(2,
        "The passage suggests that criticisms of Bronfenbrenner's model call for which of the following?",
        [
            ("A", "Its replacement with a less intricate framework"),
            ("B", "Its modification to include virtual interactions"),
            ("C", "Its replacement with a model that gives greater consideration to geographical boundaries"),
            ("D", "Its exclusion from fields such as education and public policy"),
        ],
        "B"),
    _mcq(3,
        "Which of the following best describes the influence of Ecological Systems Theory?",
        [
            ("A", "It has had little impact on psychology but has unexpectedly affected other fields."),
            ("B", "It revolutionized the field of human psychology but is not taken seriously in other fields."),
            ("C", "It changed the way human psychology is understood and continues to influence other fields."),
            ("D", "It has gone mostly unnoticed among psychologists and has had little impact on other fields."),
        ],
        "C"),
]

# 3.10 高阶 B — Space Debris: A Growing Concern
PASSAGE_3_10 = (
    "The Kessler Syndrome, proposed by NASA scientist Donald J. Kessler in "
    "1978, hypothesizes a cascading effect in low Earth orbit (LEO) in which "
    "collisions between satellites and debris—defunct satellites, spent "
    "rocket stages, and fragments from earlier collisions—generate more "
    "fragments, exponentially increasing the likelihood of further "
    "collisions. This feedback loop could render certain orbital regions "
    "unusable for decades. While the model is compelling, some assumptions "
    "merit scrutiny. For instance, it presumes a uniform distribution of "
    "debris and constant collision probability, yet orbital mechanics "
    "suggest that debris clusters in specific altitudes and orbital paths, "
    "potentially limiting the scope of cascading events.\n\n"
    "Moreover, technological advancements in debris tracking and active "
    "removal may mitigate the risk more effectively than Kessler originally "
    "envisioned. Critics argue that the syndrome underestimates the "
    "resilience of orbital infrastructure and overstates the inevitability "
    "of runaway collisions. Alternative explanations for observed debris "
    "growth include a greater number of satellite launches and fragmentation "
    "from aging spacecraft, rather than a self-sustaining cascade.\n\n"
    "Nonetheless, the Kessler Syndrome remains a valuable heuristic for "
    "space policy, emphasizing the need for international cooperation and "
    "sustainable orbital practices. Its cautionary implications are profound"
    "—especially as commercial constellations dramatically increase the "
    "number of active satellites in LEO."
)
QUESTIONS_3_10 = [
    _mcq(1,
        "The passage suggests that one impact of the Kessler Syndrome would be",
        [
            ("A", "an increase in NASA space research"),
            ("B", "a limitation on where satellites could safely orbit"),
            ("C", "a greater number of satellite launches"),
            ("D", "an increased risk of debris falling to Earth"),
        ],
        "B"),
    _mcq(2,
        "Why does the author mention the assertion that \"debris clusters in specific altitudes and orbital paths\"?",
        [
            ("A", "To provide a reason for an increase in collisions between satellites and debris"),
            ("B", "To illustrate a part of the feedback loop"),
            ("C", "To explain an objection to the Kessler Syndrome hypothesis"),
            ("D", "To emphasize the need for better debris tracking"),
        ],
        "C"),
    _mcq(3,
        "The word \"resilience\" in the passage is closest in meaning to",
        [("A", "strength"), ("B", "threat"), ("C", "knowledge"), ("D", "supervision")],
        "A"),
    _mcq(4,
        "According to the passage, some argue that the Kessler Syndrome will not occur for all of the following reasons EXCEPT:",
        [
            ("A", "Space debris may not be spread out as evenly as the theory assumes."),
            ("B", "New technology means that the removal of debris may be possible."),
            ("C", "NASA has since developed new orbital infrastructure for avoiding collisions."),
            ("D", "There may be other explanations for the observed growth in debris."),
        ],
        "C"),
    _mcq(5,
        "What does \"Its cautionary implications\" refer to in the passage?",
        [
            ("A", "The idea that one must assess the Kessler Syndrome carefully before accepting its predictions"),
            ("B", "The idea that there will be cascading collisions in LEO, making it difficult for satellites to remain intact"),
            ("C", "The suggestion that international cooperation will be more difficult to achieve as space becomes more cluttered"),
            ("D", "The suggestion that debris tracking and active removal may pose additional risks to satellites"),
        ],
        "B"),
]

# 3.27 冲刺 A — Magnetic Confinement Fusion
PASSAGE_3_27 = (
    "Magnetic confinement fusion is a promising approach for generating "
    "clean electricity. This technology fuses deuterium and tritium, heavy "
    "forms of hydrogen, to release energy while producing minimal "
    "radioactive waste when compared to current technologies to produce "
    "nuclear power. The basic principle was first demonstrated in 1957: "
    "powerful magnetic fields contain extremely hot plasma at temperatures "
    "reaching 150 million degrees Celsius—ten times hotter than the sun's "
    "core. Without magnetic containment, the plasma would instantly cool "
    "upon touching reactor walls, halting the fusion process.\n\n"
    "Since those early breakthroughs, researchers have built increasingly "
    "sophisticated magnetic confinement reactors called tokamaks. The "
    "International Thermonuclear Experimental Reactor (ITER), currently "
    "under construction, represents the culmination of decades of magnetic "
    "confinement research. ITER aims to demonstrate sustained fusion "
    "reactions that produce more energy than they consume—a critical "
    "milestone called net energy gain.\n\n"
    "However, significant challenges remain before magnetic fusion can "
    "generate commercial electricity. Current experiments require enormous "
    "energy inputs to maintain plasma conditions, and the intense neutron "
    "radiation gradually damages reactor materials. Additionally, converting "
    "fusion energy into usable electricity requires developing efficient "
    "heat-to-power conversion systems. Despite these obstacles, successful "
    "demonstration of net energy gain could pave the way for fusion power "
    "plants by the 2040s."
)
QUESTIONS_3_27 = [
    _mcq(1,
        "According to the passage, what significant achievement in fusion research occurred in 1957?",
        [
            ("A", "Researchers successfully fused deuterium and tritium atoms for the first time."),
            ("B", "Researchers demonstrated that magnetic fields could contain extremely hot plasma."),
            ("C", "Researchers estimated the temperature of the sun's core to be 150 million degrees Celsius."),
            ("D", "Researchers discovered the basic principle that explains the existence of heavy forms of hydrogen."),
        ],
        "B"),
    _mcq(2,
        "Why does the author mention plasma touching reactor walls?",
        [
            ("A", "To explain how the plasma is contained within the reactor"),
            ("B", "To point out how researchers cool plasma after heating it for experiments"),
            ("C", "To demonstrate the final step in achieving nuclear fusion"),
            ("D", "To clarify why magnetic confinement techniques are necessary"),
        ],
        "D"),
    _mcq(3,
        "The word \"sophisticated\" in the passage is closest in meaning to",
        [("A", "advanced"), ("B", "large"), ("C", "expensive"), ("D", "successful")],
        "A"),
    _mcq(4,
        "According to the passage, what is ITER's primary objective?",
        [
            ("A", "To generate commercial electricity for distribution to power grids"),
            ("B", "To demonstrate that magnetic confinement techniques are not environmentally sustainable"),
            ("C", "To prove that fusion reactions can produce more energy than they consume"),
            ("D", "To challenge decades of magnetic confinement research"),
        ],
        "C"),
    _mcq(5,
        "Which of the following is mentioned as one factor that currently prevents magnetic fusion from generating commercial electricity?",
        [
            ("A", "Insufficient global supplies of reactor materials"),
            ("B", "Inability to achieve intense neutron radiation"),
            ("C", "High energy demands for plasma maintenance"),
            ("D", "Lack of magnetic fields that are powerful enough"),
        ],
        "C"),
]

# 3.18 冲刺 B — Beyond Philosophy's Borders
PASSAGE_3_18 = (
    "Metaphilosophy is a field that looks critically at whether philosophical "
    "inquiry can truly transcend cultural and linguistic boundaries. While "
    "traditional philosophy often aims to uncover universal truths, "
    "metaphilosophy questions whether such truths are even accessible across "
    "diverse contexts. Language, far from being a neutral vessel, shapes and "
    "limits how ideas are expressed and understood. A concept that resonates "
    "deeply in one culture may carry entirely different connotations—or none "
    "at all—in another. This raises concerns about the global applicability "
    "of philosophical frameworks developed in specific cultural milieus. Are "
    "we uncovering truths, or merely reinforcing culturally contingent "
    "assumptions?\n\n"
    "Some insist that despite linguistic and cultural variation, certain "
    "philosophical concerns—like suffering, justice, or mortality—are shared "
    "across societies, suggesting a basis for universality. Yet even these "
    "themes may be interpreted through culturally specific lenses. "
    "Metaphilosophy doesn't deny the possibility of cross-cultural dialogue "
    "but cautions against assuming it is seamless. It encourages "
    "philosophers to examine how their methods and assumptions travel—or "
    "fail to—across contexts.\n\n"
    "Critics worry this reflexivity may stall progress, but others see it as "
    "essential for avoiding intellectual overreach. By foregrounding these "
    "tensions, metaphilosophy aims not to dilute philosophy's aims, but to "
    "sharpen them through greater self-awareness and methodological rigor."
)
QUESTIONS_3_18 = [
    _mcq(1,
        "According to the passage, metaphilosophy challenges which of the following basic assumptions of philosophical inquiry?",
        [
            ("A", "The world can be understood through logical analysis."),
            ("B", "Argumentation is a suitable tool for analyzing ideas."),
            ("C", "Human experience is a good source of philosophical insight."),
            ("D", "The conceptual tools that philosophy provides are universal."),
        ],
        "D"),
    _mcq(2,
        "Why does the author note that concepts may carry different connotations across different cultures?",
        [
            ("A", "To support the claim that philosophical frameworks apply globally"),
            ("B", "To illustrate the idea of crossing cultural and linguistic boundaries"),
            ("C", "To provide a justification for metaphilosophical investigations"),
            ("D", "To challenge the claim that language affects how ideas are expressed"),
        ],
        "C"),
    _mcq(3,
        "The word \"milieus\" in the passage is closest in meaning to",
        [("A", "environments"), ("B", "categories"), ("C", "centers"), ("D", "identities")],
        "A"),
    _mcq(4,
        "Which of the following is one criticism of metaphilosophy mentioned in the passage?",
        [
            ("A", "It fails to challenge existing philosophical frameworks."),
            ("B", "It may prevent philosophy from accomplishing its mission."),
            ("C", "It is used by some philosophers to keep new ideas from becoming established."),
            ("D", "It is incapable of evaluating ideas from diverse traditions."),
        ],
        "B"),
]


# ---------------------------------------------------------------------------
# Writing prompts (TOEFL Academic Discussion style, AI-authored per tier)
# ---------------------------------------------------------------------------

W_OUTLINE = (
    "评分参考（TOEFL Academic Discussion，建议 100 词以上）：\n"
    "1) Effective answer to question — 明确给出立场并直接回答教授问题；\n"
    "2) Well-developed contribution — 有具体例子或理由支撑；\n"
    "3) Language use — 句式多样、用词准确、衔接自然；\n"
    "4) 与同学观点的呼应或反驳能加分。"
)

W_VIDEO_EVIDENCE = (
    "Professor: In our recent class we discussed how technology is reshaping "
    "the criminal justice system, particularly through the use of video "
    "evidence. Some argue that body cameras and surveillance footage make "
    "court proceedings more transparent and fair. Others worry that videos "
    "can be misleading or taken out of context.\n\n"
    "In your opinion, should courts give greater weight to video evidence "
    "than to eyewitness testimony? Why or why not? Write at least 100 words."
)

W_ROMAN_LEGACY = (
    "Professor: We've been discussing how the collapse of large empires "
    "shapes the regions they once governed. Some historians argue that the "
    "fall of a centralized power leads only to instability and decline. "
    "Others point out that political fragmentation can also create space "
    "for cultural innovation and local autonomy.\n\n"
    "Which view do you find more convincing, and why? Support your position "
    "with reasons or historical examples. Write at least 100 words."
)

W_EXPERT_SYSTEMS = (
    "Professor: As artificial intelligence advances, expert systems are "
    "being introduced into professional fields like medicine, law, and "
    "engineering. Some argue these systems will improve efficiency and "
    "reduce human error. Others fear they will weaken professional "
    "judgment and reduce accountability when mistakes occur.\n\n"
    "Should companies prioritize integrating AI expert systems into "
    "high-stakes professional work? Explain your view with reasons and "
    "examples. Write at least 100 words."
)

W_CYBERNETIC = (
    "Professor: Cybernetic prosthetics now allow amputees to perform tasks "
    "that were once impossible. However, these devices remain costly, and "
    "access is uneven across socioeconomic groups. Some argue governments "
    "should subsidize advanced prosthetics for everyone who needs them. "
    "Others believe public funding should focus on more basic medical "
    "needs first.\n\n"
    "Which position do you support, and why? Use specific reasoning to "
    "develop your answer. Write at least 100 words."
)

W_ECOLOGICAL = (
    "Professor: Bronfenbrenner's Ecological Systems Theory argues that a "
    "child's development is shaped by multiple overlapping environments — "
    "family, school, community, and broader culture. Critics now argue the "
    "theory must account for virtual microsystems (social media, online "
    "communities) that no longer respect geographical boundaries.\n\n"
    "How important do you think online environments are in shaping today's "
    "students compared with traditional environments like family and "
    "school? Develop your view with examples. Write at least 100 words."
)

W_SPACE_DEBRIS = (
    "Professor: As more private companies launch satellite constellations, "
    "low Earth orbit is becoming increasingly crowded. Some argue that "
    "international regulation is urgently needed to prevent the Kessler "
    "Syndrome from occurring. Others say private innovation will solve the "
    "problem faster than slow-moving treaties.\n\n"
    "Which approach — international regulation or private innovation — do "
    "you think is more likely to solve the space debris problem? Justify "
    "your view. Write at least 100 words."
)

W_FUSION = (
    "Professor: Magnetic confinement fusion promises clean, nearly limitless "
    "energy, but successful commercial reactors are likely decades away. "
    "Some governments are investing heavily in fusion research now. Others "
    "argue this funding should instead support proven renewable "
    "technologies like wind and solar that can address climate change "
    "today.\n\n"
    "If you had to advise a national energy minister, would you prioritize "
    "fusion research or proven renewables? Explain your reasoning with "
    "specific arguments. Write at least 100 words."
)

W_METAPHILOSOPHY = (
    "Professor: Metaphilosophy questions whether philosophical concepts "
    "developed in one cultural tradition can meaningfully apply to others. "
    "Some scholars insist that values like justice, truth, and dignity are "
    "universal. Others argue that translating these concepts across "
    "languages and cultures inevitably distorts their meaning.\n\n"
    "Do you believe that any philosophical concepts are truly universal "
    "across cultures? Defend your position with examples or reasoning. "
    "Write at least 100 words."
)


# ---------------------------------------------------------------------------
# Paper definitions
# ---------------------------------------------------------------------------

def _make_paper(title, level, tier_label, description, passage_title,
                passage, questions, writing_prompt, reading_minutes=14):
    return {
        "title": title,
        "exam_type": "toefl",
        "level": level,
        "description": description,
        "sections": [
            {
                "section_type": "reading",
                "sequence": 1,
                "title": f"Section 1 · Reading — {passage_title}",
                "instructions": (
                    "阅读下面的学术文章并回答选择题。每题只有一个最佳答案。\n"
                    f"建议时间：{reading_minutes} 分钟。"
                ),
                "audio_url": None,
                "passage": passage,
                "duration_minutes": reading_minutes,
                "questions": questions,
            },
            {
                "section_type": "writing",
                "sequence": 2,
                "title": "Section 2 · Writing (Academic Discussion)",
                "instructions": (
                    "阅读教授的提问和上下文，写出你的回应。建议字数 100 词以上；"
                    "时间紧张可只写立场 + 1-2 句理由。"
                ),
                "audio_url": None,
                "passage": None,
                "duration_minutes": 10,
                "questions": [
                    {
                        "sequence": 1,
                        "question_type": "essay",
                        "stem": writing_prompt,
                        "options_json": None,
                        "correct_answer": None,
                        "points": 5,
                        "reference_answer": W_OUTLINE,
                    }
                ],
            },
        ],
    }


PAPERS = [
    # ---- 入门 60-80 ----
    _make_paper(
        "新版 TOEFL 入门诊断 A · Video Evidence",
        "toefl_60_80",
        "入门 (60-80)",
        "适用于 TOEFL 预估 60-80 分学生（入门档 A 套）。基于 2026.4.6 真题阅读改编，主题为视频证据在法庭的应用，5 道选择题 + 1 道 Academic Discussion 写作题。约 25 分钟。",
        "Video Evidence in U.S. Courts",
        PASSAGE_4_6, QUESTIONS_4_6, W_VIDEO_EVIDENCE,
    ),
    _make_paper(
        "新版 TOEFL 入门诊断 B · Roman Empire Legacy",
        "toefl_60_80",
        "入门 (60-80)",
        "适用于 TOEFL 预估 60-80 分学生（入门档 B 套）。基于 2026.3.30 真题阅读改编，主题为罗马帝国崩溃的政治影响，4 道选择题 + 1 道 Academic Discussion 写作题。约 22 分钟。",
        "The Political Legacy of the Roman Empire",
        PASSAGE_3_30, QUESTIONS_3_30, W_ROMAN_LEGACY,
    ),
    # ---- 中阶 80-95 ----
    _make_paper(
        "新版 TOEFL 中阶诊断 A · Expert Systems",
        "toefl_80_95",
        "中阶 (80-95)",
        "适用于 TOEFL 预估 80-95 分学生（中阶档 A 套）。基于 2026.4.5 真题阅读改编，主题为专家系统与 MYCIN 案例，4 道选择题 + 1 道 Academic Discussion 写作题。约 22 分钟。",
        "Expert Systems",
        PASSAGE_4_5, QUESTIONS_4_5, W_EXPERT_SYSTEMS,
    ),
    _make_paper(
        "新版 TOEFL 中阶诊断 B · Cybernetic Prosthetics",
        "toefl_80_95",
        "中阶 (80-95)",
        "适用于 TOEFL 预估 80-95 分学生（中阶档 B 套）。基于 2026.4.8 真题阅读改编，主题为神经控制义肢，3 道选择题 + 1 道 Academic Discussion 写作题。约 20 分钟。",
        "Cybernetic Prosthetics",
        PASSAGE_4_8, QUESTIONS_4_8, W_CYBERNETIC,
    ),
    # ---- 高阶 95-105 ----
    _make_paper(
        "新版 TOEFL 高阶诊断 A · Ecological Systems Theory",
        "toefl_95_105",
        "高阶 (95-105)",
        "适用于 TOEFL 预估 95-105 分学生（高阶档 A 套）。基于 2026.4.1 真题阅读改编，主题为 Bronfenbrenner 生态系统理论，3 道选择题 + 1 道 Academic Discussion 写作题。约 20 分钟。",
        "Understanding Ecological Systems Theory",
        PASSAGE_4_1, QUESTIONS_4_1, W_ECOLOGICAL,
    ),
    _make_paper(
        "新版 TOEFL 高阶诊断 B · Space Debris",
        "toefl_95_105",
        "高阶 (95-105)",
        "适用于 TOEFL 预估 95-105 分学生（高阶档 B 套）。基于 2026.3.10 真题阅读改编，主题为 Kessler Syndrome 与太空碎片，5 道选择题 + 1 道 Academic Discussion 写作题。约 25 分钟。",
        "Space Debris: A Growing Concern",
        PASSAGE_3_10, QUESTIONS_3_10, W_SPACE_DEBRIS,
    ),
    # ---- 冲刺 105+ ----
    _make_paper(
        "新版 TOEFL 冲刺诊断 A · Magnetic Confinement Fusion",
        "toefl_105_plus",
        "冲刺 (105+)",
        "适用于 TOEFL 预估 105 分以上学生（冲刺档 A 套）。基于 2026.3.27 真题阅读改编，主题为磁约束核聚变与 ITER 项目，5 道选择题 + 1 道 Academic Discussion 写作题。约 25 分钟。",
        "Magnetic Confinement Fusion",
        PASSAGE_3_27, QUESTIONS_3_27, W_FUSION,
    ),
    _make_paper(
        "新版 TOEFL 冲刺诊断 B · Beyond Philosophy's Borders",
        "toefl_105_plus",
        "冲刺 (105+)",
        "适用于 TOEFL 预估 105 分以上学生（冲刺档 B 套）。基于 2026.3.18 真题阅读改编，主题为元哲学与跨文化普遍性，4 道选择题 + 1 道 Academic Discussion 写作题。约 22 分钟。",
        "Beyond Philosophy's Borders",
        PASSAGE_3_18, QUESTIONS_3_18, W_METAPHILOSOPHY,
    ),
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def _get_default_creator_id():
    user = User.query.filter(User.role.in_(("admin", "teacher"))).first()
    if not user:
        user = User.query.first()
    return user.id if user else None


def seed_paper(data, creator_id):
    existing = EntranceTestPaper.query.filter_by(
        title=data["title"], exam_type=data["exam_type"]
    ).first()
    if existing:
        print(f"  [SKIP] '{data['title']}' already exists (id={existing.id})")
        return existing

    paper = EntranceTestPaper(
        title=data["title"],
        exam_type=data["exam_type"],
        level=data["level"],
        description=data["description"],
        is_active=True,
        created_by=creator_id,
    )
    db.session.add(paper)
    db.session.flush()

    for sec_data in data["sections"]:
        section = EntranceTestSection(
            paper_id=paper.id,
            section_type=sec_data["section_type"],
            sequence=sec_data["sequence"],
            title=sec_data["title"],
            instructions=sec_data["instructions"],
            audio_url=sec_data.get("audio_url"),
            passage=sec_data.get("passage"),
            duration_minutes=sec_data["duration_minutes"],
        )
        db.session.add(section)
        db.session.flush()

        for q_data in sec_data["questions"]:
            question = EntranceTestQuestion(
                section_id=section.id,
                sequence=q_data["sequence"],
                question_type=q_data["question_type"],
                stem=q_data["stem"],
                options_json=q_data.get("options_json"),
                correct_answer=q_data.get("correct_answer"),
                points=q_data["points"],
                reference_answer=q_data.get("reference_answer"),
            )
            db.session.add(question)

    db.session.commit()
    n_q = sum(len(s["questions"]) for s in data["sections"])
    print(f"  [CREATED] '{data['title']}' (id={paper.id}, {n_q} questions)")
    return paper


def main():
    with app.app_context():
        creator_id = _get_default_creator_id()
        if not creator_id:
            print("Error: no user in DB to own the papers. Create an admin first.")
            sys.exit(1)

        print(f"Seeding TOEFL tiered papers (creator user id={creator_id})...")
        for data in PAPERS:
            seed_paper(data, creator_id)
        print("Done.")


if __name__ == "__main__":
    main()
