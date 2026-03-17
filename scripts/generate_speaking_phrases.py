#!/usr/bin/env python3
"""Generate TOEFL Listen-and-Repeat speaking practice Excel files.

Creates 12 topic-based Excel files, each with 10-15 high-frequency sentences
that commonly appear in TOEFL speaking repeat tasks. Each file can be uploaded
via the admin /api/speaking/books endpoint.

Topics: Museum, Library, Hotel, Fitness Center, Store, Campus Tour,
        Nature Places, Community Center, Car Rental, Orientation, Office, Festival
"""

import os
import openpyxl

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "speaking_phrases")

TOPICS = {
    "Museum": [
        ("The museum offers free admission on the first Sunday of every month.", "博物馆每月第一个周日免费开放。"),
        ("You can pick up an audio guide at the front desk.", "你可以在前台领取语音导览器。"),
        ("The exhibit on ancient Egypt is located on the second floor.", "古埃及展览位于二楼。"),
        ("Photography is not permitted in the special exhibition hall.", "特展厅内不允许拍照。"),
        ("The museum shop sells postcards and souvenirs related to the collections.", "博物馆商店出售与馆藏相关的明信片和纪念品。"),
        ("Guided tours are available in English and Spanish.", "提供英语和西班牙语的导览服务。"),
        ("The museum was renovated last year and now has a modern wing.", "博物馆去年翻新了，现在有一个现代展区。"),
        ("Please do not touch the artwork on display.", "请勿触碰展出的艺术品。"),
        ("The permanent collection features impressionist paintings.", "永久馆藏以印象派画作为主。"),
        ("There is a café on the ground floor where you can grab a quick bite.", "一楼有一个咖啡厅，你可以在那里简单用餐。"),
        ("Membership gives you unlimited access to all exhibits year-round.", "会员资格让你全年无限次参观所有展览。"),
        ("The museum hosts a lecture series every Wednesday evening.", "博物馆每周三晚上举办系列讲座。"),
    ],
    "Library": [
        ("You need a valid student ID to check out books.", "你需要有效的学生证才能借书。"),
        ("The library has an extensive collection of academic journals.", "图书馆拥有大量的学术期刊。"),
        ("Books can be renewed online up to three times.", "图书可以在网上续借最多三次。"),
        ("The quiet study area is on the third floor.", "安静的自习区在三楼。"),
        ("There is a fine of fifty cents per day for overdue books.", "逾期图书每天罚款五十美分。"),
        ("The library offers free workshops on research methods.", "图书馆提供免费的研究方法讲座。"),
        ("You can reserve a group study room through the library website.", "你可以通过图书馆网站预约小组自习室。"),
        ("The reference section is for in-library use only.", "参考资料区仅供馆内使用。"),
        ("Interlibrary loan requests usually take about a week.", "馆际互借申请通常需要大约一周时间。"),
        ("The computer lab on the second floor has printing services.", "二楼的电脑室提供打印服务。"),
        ("The library extends its hours during final exam week.", "期末考试周图书馆会延长开放时间。"),
        ("Digital resources can be accessed remotely with your library account.", "你可以用图书馆账户远程访问数字资源。"),
    ],
    "Hotel": [
        ("Check-in time is at three in the afternoon and check-out is at noon.", "入住时间为下午三点，退房时间为中午十二点。"),
        ("Could I get a room with a view of the ocean?", "我能要一间海景房吗？"),
        ("The hotel provides a complimentary breakfast buffet every morning.", "酒店每天早上提供免费的自助早餐。"),
        ("Room service is available twenty-four hours a day.", "客房服务全天24小时提供。"),
        ("You can leave your luggage at the front desk after check-out.", "退房后你可以把行李寄存在前台。"),
        ("The fitness center and swimming pool are on the top floor.", "健身中心和游泳池在顶楼。"),
        ("We offer a shuttle service to and from the airport.", "我们提供往返机场的班车服务。"),
        ("Please press five on the phone to reach the concierge.", "请按电话上的5键联系礼宾服务。"),
        ("Extra towels and pillows can be requested at the front desk.", "你可以在前台索取额外的毛巾和枕头。"),
        ("The hotel has a business center with printing and fax machines.", "酒店设有配备打印机和传真机的商务中心。"),
        ("Would you like a wake-up call tomorrow morning?", "你需要明早的叫醒服务吗？"),
        ("Late check-out is available for an additional fee.", "延迟退房需要额外收费。"),
    ],
    "Fitness Center": [
        ("The gym is open from six in the morning until ten at night.", "健身房的开放时间为早上六点到晚上十点。"),
        ("You need to sign up for a membership before using the facilities.", "使用设施前你需要注册会员。"),
        ("Personal training sessions can be booked at the front desk.", "私教课程可以在前台预约。"),
        ("Please wipe down the equipment after each use.", "使用完器材后请擦拭干净。"),
        ("The yoga class starts at seven thirty on Monday and Wednesday mornings.", "瑜伽课在周一和周三早上七点半开始。"),
        ("Lockers are available in the changing room but you need to bring your own lock.", "更衣室有储物柜，但你需要自带锁。"),
        ("The swimming pool requires a separate pass.", "使用游泳池需要单独的通行证。"),
        ("We offer a free trial week for new members.", "我们为新会员提供一周免费试用。"),
        ("The group fitness schedule is posted on the bulletin board.", "团体健身课表张贴在公告栏上。"),
        ("Towels and water bottles are provided at the entrance.", "入口处提供毛巾和水瓶。"),
        ("The spinning class has been moved to Studio B starting next week.", "从下周开始，动感单车课搬到B教室了。"),
        ("You can freeze your membership for up to three months.", "你可以冻结会员资格最多三个月。"),
    ],
    "Store": [
        ("The store is having a clearance sale this weekend.", "这家店这个周末有清仓特卖。"),
        ("All items on this rack are twenty percent off.", "这个架子上的所有商品打八折。"),
        ("Do you have this shirt in a larger size?", "这件衬衫有大一号的吗？"),
        ("The fitting rooms are at the back of the store.", "试衣间在商店后面。"),
        ("We accept cash, credit cards, and mobile payments.", "我们接受现金、信用卡和手机支付。"),
        ("You can return items within thirty days with the original receipt.", "凭原始收据可以在三十天内退货。"),
        ("This item is currently out of stock but we can order it for you.", "这件商品目前缺货，但我们可以帮你订购。"),
        ("The electronics section is on the second floor.", "电子产品区在二楼。"),
        ("Would you like a bag or did you bring your own?", "你需要袋子还是自己带了？"),
        ("Our loyalty program gives you points for every dollar you spend.", "我们的会员计划让你每消费一美元都能积分。"),
        ("The new collection just arrived yesterday.", "新款昨天刚到。"),
        ("We offer free gift wrapping during the holiday season.", "节日期间我们提供免费礼品包装。"),
    ],
    "Campus Tour": [
        ("Welcome to the campus. I will be your guide for today's tour.", "欢迎来到校园。我将是你今天的导游。"),
        ("The main library is the large building to your left.", "主图书馆是你左边那栋大楼。"),
        ("The dining hall serves breakfast, lunch, and dinner.", "食堂供应早餐、午餐和晚餐。"),
        ("Student housing is located on the north side of campus.", "学生宿舍位于校园的北侧。"),
        ("The science laboratories were recently upgraded with new equipment.", "科学实验室最近更新了设备。"),
        ("There are over two hundred student organizations you can join.", "有两百多个学生社团你可以加入。"),
        ("The campus has its own health center with a full-time physician.", "校园有自己的医疗中心，配有全职医生。"),
        ("This building houses the admissions office and financial aid.", "这栋楼是招生办和助学金办公室所在地。"),
        ("The recreational center has a rock climbing wall and an indoor track.", "活动中心有攀岩墙和室内跑道。"),
        ("Shuttle buses run every fifteen minutes between the main campus and the dorms.", "班车每十五分钟一班，往返于主校区和宿舍之间。"),
        ("The campus bookstore sells textbooks as well as university merchandise.", "校园书店出售教材和大学纪念品。"),
        ("We encourage all prospective students to sit in on a class during the visit.", "我们鼓励所有准学生在参观期间旁听一节课。"),
    ],
    "Nature Places": [
        ("The hiking trail is about five miles long and takes roughly three hours.", "这条登山步道大约五英里长，大约需要三小时。"),
        ("Please stay on the marked path to protect the vegetation.", "请沿标记的路径行走，以保护植被。"),
        ("The national park is home to over three hundred species of birds.", "这座国家公园有三百多种鸟类。"),
        ("Camping permits must be obtained at the ranger station.", "露营许可证必须在护林站领取。"),
        ("The best time to visit the waterfall is in the spring after the snow melts.", "参观瀑布的最佳时间是春天雪融之后。"),
        ("Visitors are not allowed to feed or approach the wildlife.", "游客不得喂食或接近野生动物。"),
        ("The scenic overlook offers a breathtaking view of the valley.", "观景台可以看到令人叹为观止的山谷景色。"),
        ("Sunscreen and insect repellent are strongly recommended.", "强烈建议涂抹防晒霜和驱虫剂。"),
        ("The botanical garden features plants from five different climate zones.", "植物园展示了五个不同气候带的植物。"),
        ("There is a visitor center at the entrance with maps and brochures.", "入口处有一个游客中心，提供地图和小册子。"),
        ("Fishing is permitted in the lake with a valid license.", "持有效许可证可以在湖中钓鱼。"),
        ("The park closes at sunset and reopens at sunrise.", "公园日落关闭，日出重新开放。"),
    ],
    "Community Center": [
        ("The community center offers free classes for senior citizens.", "社区中心为老年人提供免费课程。"),
        ("Registration for summer programs begins in April.", "暑期课程的注册从四月开始。"),
        ("The center has a large meeting room that can be rented for events.", "中心有一个可以租用举办活动的大会议室。"),
        ("After-school tutoring is available Monday through Thursday.", "周一到周四提供课后辅导。"),
        ("The community garden is open to all residents in the neighborhood.", "社区花园向附近所有居民开放。"),
        ("Volunteers are needed for the weekend food drive.", "周末的食物募捐活动需要志愿者。"),
        ("Art and music classes are held in the west wing of the building.", "美术和音乐课在大楼的西翼举行。"),
        ("The center hosts a farmers' market every Saturday morning.", "中心每周六早上举办农贸市场。"),
        ("You can sign up for the newsletter to stay informed about upcoming events.", "你可以订阅新闻通讯以了解即将举行的活动。"),
        ("The basketball court is available on a first-come, first-served basis.", "篮球场先到先得。"),
        ("There is a childcare room available during adult classes.", "成人课程期间有托儿室可供使用。"),
    ],
    "Car Rental": [
        ("I would like to rent a mid-size sedan for three days.", "我想租一辆中型轿车三天。"),
        ("The daily rate includes unlimited mileage.", "日租价包含不限里程。"),
        ("You will need a valid driver's license and a credit card.", "你需要有效的驾照和信用卡。"),
        ("Would you like to add insurance coverage to your rental?", "你要为租车添加保险吗？"),
        ("The car must be returned with a full tank of gas.", "还车时油箱必须加满。"),
        ("We have compact, mid-size, and full-size vehicles available.", "我们有紧凑型、中型和大型车辆可供选择。"),
        ("There is an additional charge for dropping the car off at a different location.", "在不同地点还车需要额外收费。"),
        ("GPS navigation can be added for ten dollars a day.", "GPS导航每天加收十美元。"),
        ("Please inspect the vehicle for any existing damage before you drive off.", "开走之前请检查车辆是否有已有的损伤。"),
        ("The rental agreement covers roadside assistance in case of a breakdown.", "租赁协议包含车辆故障时的道路救援。"),
        ("You can extend your rental by calling us at least twenty-four hours in advance.", "你可以提前至少二十四小时打电话给我们延长租期。"),
        ("An additional driver can be added to the policy for a small fee.", "可以少量收费将额外驾驶员添加到保单中。"),
    ],
    "Orientation": [
        ("Welcome to freshman orientation. We are glad to have you here.", "欢迎参加新生迎新会。我们很高兴你的到来。"),
        ("You will receive your student ID card at the end of today's session.", "你将在今天的活动结束时领取学生证。"),
        ("Academic advising appointments can be made through the online portal.", "学业咨询预约可以通过在线平台进行。"),
        ("Each student is assigned a faculty advisor in their major department.", "每位学生都会被分配一位所在专业的教师顾问。"),
        ("The deadline for adding or dropping courses is the second week of the semester.", "加课或退课的截止日期是学期的第二周。"),
        ("Tutoring services are free and available at the learning center.", "辅导服务免费，可在学习中心获得。"),
        ("The campus safety office is open around the clock.", "校园安全办公室全天候开放。"),
        ("Make sure to activate your email account before classes begin.", "确保在上课前激活你的电子邮箱账号。"),
        ("The writing center can help you with essays and research papers.", "写作中心可以帮助你完成论文和研究报告。"),
        ("Student health insurance is mandatory for all full-time students.", "所有全日制学生都必须购买学生健康保险。"),
        ("There will be a campus-wide social event this Friday evening.", "本周五晚上将举行全校社交活动。"),
        ("Please download the campus app for maps, schedules, and emergency alerts.", "请下载校园应用以获取地图、课表和紧急通知。"),
    ],
    "Office": [
        ("The meeting has been moved from two o'clock to three thirty.", "会议从两点改到了三点半。"),
        ("Could you send me the report by the end of the day?", "你能在今天下班前把报告发给我吗？"),
        ("The printer on this floor is out of order. Please use the one downstairs.", "这层的打印机坏了，请使用楼下的。"),
        ("All employees need to complete the safety training by Friday.", "所有员工需要在周五之前完成安全培训。"),
        ("The conference room needs to be reserved in advance through the system.", "会议室需要通过系统提前预约。"),
        ("Please make sure to update the shared spreadsheet with your progress.", "请确保在共享表格中更新你的进度。"),
        ("The office will be closed next Monday for the public holiday.", "下周一因公共假日办公室将关闭。"),
        ("New office supplies can be ordered through the procurement portal.", "新的办公用品可以通过采购平台订购。"),
        ("The IT department will be upgrading the network this weekend.", "IT部门本周末将升级网络。"),
        ("Please remember to sign in at the reception when you arrive.", "到达时请记得在前台签到。"),
        ("The parking garage is full so you may need to use the overflow lot.", "停车场满了，你可能需要使用溢出停车区。"),
        ("Staff are encouraged to join the wellness program starting next month.", "鼓励员工参加下个月开始的健康计划。"),
    ],
    "Festival": [
        ("The annual music festival will be held in the park this Saturday.", "一年一度的音乐节本周六在公园举行。"),
        ("Tickets can be purchased online or at the box office.", "门票可以在网上或售票处购买。"),
        ("The parade starts at ten in the morning and goes along Main Street.", "游行从早上十点开始，沿主街进行。"),
        ("There will be food stalls offering dishes from around the world.", "会有来自世界各地美食的小吃摊位。"),
        ("The fireworks display begins at nine o'clock in the evening.", "烟花表演在晚上九点开始。"),
        ("Children under twelve can enter the festival for free.", "十二岁以下的儿童可以免费入场。"),
        ("Live performances will take place on the main stage throughout the day.", "全天都有现场表演在主舞台进行。"),
        ("Volunteers are needed to help set up the booths.", "需要志愿者帮忙搭建摊位。"),
        ("The art fair features works by local artists and craftspeople.", "艺术展展出当地艺术家和工匠的作品。"),
        ("Free parking is available at the lot behind the community center.", "社区中心后面的停车场提供免费停车。"),
        ("The festival celebrates the town's cultural heritage and traditions.", "这个节日庆祝小镇的文化遗产和传统。"),
        ("In case of rain, the event will be moved to the indoor arena.", "如果下雨，活动将转移到室内体育馆。"),
    ],
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for topic, sentences in TOPICS.items():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = topic
        ws.append(["sentence", "translation"])
        for eng, chn in sentences:
            ws.append([eng, chn])

        # Auto-width
        ws.column_dimensions["A"].width = 70
        ws.column_dimensions["B"].width = 40

        fname = f"TOEFL_Speaking_{topic.replace(' ', '_')}.xlsx"
        path = os.path.join(OUT_DIR, fname)
        wb.save(path)
        print(f"  ✓ {fname} ({len(sentences)} sentences)")

    print(f"\nDone! {len(TOPICS)} files saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
