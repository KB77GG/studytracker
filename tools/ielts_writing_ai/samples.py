"""Built-in synthetic essays for the real-model check (written for this tool; no
student data). Expected ranges are deliberately wide sanity bounds, not true IELTS
scores: they catch a model that inflates, ignores the question or scores randomly.
"""

from __future__ import annotations

TRANSPORT_PROMPT = (
    "Some people think that governments should spend money on improving public transport "
    "rather than building new roads. To what extent do you agree or disagree?"
)

WEAK = """Nowadays transport is very important problem in many country. Some people think goverment should spend money for public transport not for build new road. I am agree with this opinion in some way but not all.

Firstly, public transport is good for people. Because many people dont have car and they need bus and train to go work and school. If the bus is more better, people will use it more and the traffic will be less. In my city the bus is always late and very crowd so people dont like to take it. Also the train is too expensive for student. So goverment should make it cheap and more fast.

Secondly, new road is also important. Because the city is grow and more people buy car every year. If there is no new road the traffic jam will be very bad and people waste a lot of time. For example my father drive to work everyday and he spend two hour in the road. This is very bad for him and for the economy also.

But I think public transport is more important than road. Because the road make more car and more pollution. The public transport can carry many people in one time and it is good for enviroment. Also if more people take bus, the city will be more quiet and the air will be more clean, so everybody can be more healthy and happy.

In conclusion, I think goverment should spend more money for public transport but also build some road when it is necessary. Both is important for the people and the country develop."""

MID = """In many cities, traffic congestion has become a serious problem, and governments must decide how to use limited budgets. Some people argue that money should go to public transport instead of new roads. I mostly agree with this view, although I believe some road building is still necessary.

The main reason to invest in public transport is that it can move a large number of people efficiently. A single train can carry hundreds of passengers, while the same number of people would need hundreds of cars. If buses and trains are frequent, cheap and reliable, many drivers will choose them, which will reduce traffic jams. For example, after my city opened a new metro line, the main road to the city centre became much less crowded during rush hour.

Another advantage is the environment. Cars produce a lot of air pollution and carbon emissions, which are harmful to people's health and contribute to climate change. Public transport produces less pollution per passenger, so it is a more sustainable option in the long term.

On the other hand, new roads are sometimes needed. In rural areas, there are not enough passengers to make train lines profitable, so people depend on cars. Also, goods are mostly transported by trucks, and poor roads can slow down the economy.

In conclusion, I agree that governments should give priority to public transport because it is more efficient and better for the environment. However, they should still build roads in places where public transport is not practical."""

GOOD = """As urban populations grow, governments face a difficult choice about where to direct transport spending. While some advocate building more roads to ease congestion, I largely agree that public transport deserves the greater share of investment, because it addresses the causes of traffic problems rather than merely their symptoms.

The strongest argument for prioritising public transport is efficiency. Roads are an inherently limited resource: a lane of motorway can carry only a fixed number of private vehicles per hour, whereas a well-run rail or bus rapid transit line can move many times that number of people in the same space. Moreover, there is considerable evidence that new roads tend to fill up quickly, as cheaper and faster journeys encourage more people to drive. Expanding road networks may therefore offer only temporary relief before congestion returns.

Public transport also brings wider social and environmental benefits. It gives affordable mobility to those who cannot drive, such as students, the elderly and lower-income workers, thereby widening their access to jobs and services. At the same time, shifting journeys from cars to trains and buses reduces both air pollution and greenhouse gas emissions, which is increasingly important as cities attempt to meet climate targets.

Nevertheless, it would be unrealistic to stop road building altogether. In sparsely populated regions, buses and trains are rarely viable, and freight still relies heavily on trucks. Targeted road improvements, such as bypasses around congested towns, can therefore remain a sensible use of funds.

In conclusion, although some road investment is still justified, governments should concentrate their spending on public transport, since it offers a more lasting solution to congestion while also delivering social and environmental gains."""

STRONG = """How a government allocates its transport budget shapes not only how quickly people travel, but also the kind of cities they live in. Although there is an intuitive appeal to building new roads whenever traffic worsens, I am convinced that investment should be weighted decisively towards public transport, with road construction reserved for cases where no realistic alternative exists.

The case for new roads rests largely on the assumption that congestion is a shortage of capacity. Yet experience from many large cities suggests otherwise: widening a motorway lowers the cost of driving, which in turn draws additional traffic until the new lanes are as clogged as the old ones. This phenomenon, often described as induced demand, means that road building can become an expensive treadmill. Public transport, by contrast, increases the number of people a corridor can carry without a proportional increase in the space consumed, and a single metro line can relieve pressure on an entire network of streets.

Equally important are the distributional consequences. Road spending disproportionately benefits those who own cars, whereas frequent and affordable buses and trains extend opportunity to people who cannot or prefer not to drive. Well-designed transit also allows denser, more walkable neighbourhoods to develop around stations, reducing the distances people need to travel in the first place, and it cuts emissions at a time when the transport sector remains one of the most stubborn sources of carbon.

That said, a blanket refusal to build roads would be misguided. Rural communities and freight logistics depend on reliable highways, and in such contexts targeted upgrades may represent genuine value for money.

On balance, therefore, public transport should receive the lion's share of funding, because it tackles congestion at its root and produces broader social and environmental returns that new roads rarely match."""

OFF_TOPIC = """Online learning has grown rapidly over the past decade, and many people now believe that it will eventually replace traditional classrooms. In my view, although online courses offer clear advantages, face-to-face education will remain essential.

The most obvious benefit of online learning is flexibility. Students can watch lectures at any time and study at their own pace, which is especially useful for adults who work full-time or have family responsibilities. Online courses can also reach learners in remote areas who would otherwise have no access to good teachers. In addition, digital materials can be updated quickly, and learners can replay difficult explanations as many times as they need, which is impossible in a traditional lecture. For many people, these features make online study cheaper and more convenient than attending a college in person.

However, classroom learning provides things that are difficult to replicate on a screen. Teachers can notice immediately when a student is confused and adapt their explanations. Students also develop social skills by working together, discussing ideas and building friendships, which are an important part of education, particularly for children.

Furthermore, many learners find it hard to stay motivated without the structure of a timetable and the presence of classmates. Completion rates for many free online courses are notoriously low, which suggests that self-discipline is a serious obstacle.

In conclusion, online learning is a valuable supplement that makes education more accessible and flexible, but it is unlikely to replace traditional classrooms, which offer interaction, support and motivation that technology cannot fully provide."""

UNDER_LENGTH = """I agree that governments should spend more money on public transport than on new roads. Public transport can carry many people at the same time, so it reduces traffic jams in big cities. It is also cheaper for students and old people who do not have cars. In addition, buses and trains produce less pollution than private cars, which is good for the environment and for public health. However, new roads are still useful in the countryside, where there are not many buses. In conclusion, public transport should be the priority, but some roads are still necessary."""

TASK1_PROMPT = (
    "The bar chart below shows the percentage of households that owned a car in four "
    "countries in 2000 and 2020. Summarise the information by selecting and reporting the "
    "main features, and make comparisons where relevant."
)

TASK1_NO_IMAGE = """The bar chart compares the proportion of households with a car in four countries in 2000 and 2020.

Overall, car ownership increased in all four countries over the period, although the size of the rise varied considerably. Country A had the highest level of ownership in both years, while Country D remained the lowest.

In 2000, around 70% of households in Country A owned a car, compared with roughly 55% in Country B and about 40% in Country C. Country D had by far the lowest figure, at only 15%.

By 2020, the percentage in Country A had risen slightly to about 75%, and Country B had grown to approximately 65%. The most dramatic change was seen in Country C, where ownership almost doubled to nearly 80%, overtaking Country A. Country D also experienced significant growth, reaching around 35%, but it was still well behind the other three countries.

In summary, while every country saw an increase, the growth was particularly striking in Country C and much more modest in Country A."""

# expect: optional sanity bounds checked by the report.
SAMPLES = [
    {
        "id": "t2-weak",
        "task_type": "task2",
        "prompt": TRANSPORT_PROMPT,
        "essay": WEAK,
        "level": 1,
        "expect": {"overall_max": 5.5, "argument_min_problems": 1},
    },
    {
        "id": "t2-mid",
        "task_type": "task2",
        "prompt": TRANSPORT_PROMPT,
        "essay": MID,
        "level": 2,
        "expect": {"overall_min": 5.0, "overall_max": 7.0},
    },
    {
        "id": "t2-good",
        "task_type": "task2",
        "prompt": TRANSPORT_PROMPT,
        "essay": GOOD,
        "level": 3,
        "expect": {"overall_min": 6.0, "overall_max": 8.0},
    },
    {
        "id": "t2-strong",
        "task_type": "task2",
        "prompt": TRANSPORT_PROMPT,
        "essay": STRONG,
        "level": 4,
        "expect": {
            "overall_min": 7.0,
            "argument_max_problems": 1,
            "argument_forbid": [
                "off_position",
                "unclear_position",
                "inconsistent_position",
                "conclusion_inconsistent",
            ],
            "argument_position": True,
        },
    },
    {
        "id": "t2-off-topic",
        "task_type": "task2",
        "prompt": TRANSPORT_PROMPT,
        "essay": OFF_TOPIC,
        "expect": {"task_max": 5.0, "argument_any_of": ["off_position", "irrelevant"]},
    },
    {
        "id": "t2-under-length",
        "task_type": "task2",
        "prompt": TRANSPORT_PROMPT,
        "essay": UNDER_LENGTH,
        "expect": {"word_warning": True},
    },
    {
        "id": "t1-no-image",
        "task_type": "task1",
        "prompt": TASK1_PROMPT,
        "essay": TASK1_NO_IMAGE,
        # Built-in contradiction: A "highest in both years" vs C overtaking A in 2020.
        "expect": {"not_assessable": True, "consistency_min": 1},
    },
]
