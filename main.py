import time

from func import *
from config import *
import re
from playwright.sync_api import sync_playwright

buy_price = 0

# 判断数据是否获取到
def load_webpage(page):


    while True:

        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        print(f"📌 页面加载中")
        print("滚动到页面顶部")
        scroll_target_page_human(page, direction="top", scroll_target="page", mode="fast",port=port)

        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        # 价格页面固动条拉到最高，这个是这个框框内的滚动条，要获取最外层的路径
        print("成交记录滚动到顶部")
        target_xpath = "(//*[contains(@class, 'flexlayout__tab_moveable')])[3]//*[@tabindex='0' and @aria-label='grid']"
        scroll_target_page_human(page, xpath=target_xpath, direction="top", scroll_target="element",
                                 mode="fast",port=port)


        try:
            target_xpath = "(//*[contains(@class, 'ReactVirtualized__Grid__innerScrollContainer')]//*[contains(@class, 'flex-1') and contains(@class, 'cursor-pointer')])[1]"
            global buy_price
            buy_price = get_xpath_value_by_url(page, target_xpath, debug=True,port=port)

            if buy_price is not None and float(buy_price) > 0:
                try:

                    print("📌 价格数据加载完成,开始运行")
                    break
                except ValueError:
                    print("⚠️ 非数字内容，跳过")
            else:
                print("获取不到元素，继续加载，或者请检查")

        except Exception as e:
            print(f"⚠️ 错误：{e}")

        time.sleep(10)

# 刷新页面
def refresh_url(text):

    print(text)
    scroll_target_page_human(page, direction="top", scroll_target="page", mode="fast", port=port)
    xpath = "(//*[contains(@class, 'bg-BasicBg')]//*[contains(@class, 'items-center')]//*[contains(@class, 'text-PrimaryText')])[1]"
    refresh_specific_page_until_element(page, target_url, xpath, delay=60, debug=True)


def execute_sell():

    # 先进行卖出的操作
    # 点击第 0 个 tab
    #  监控谷歌验证器弹窗暂停程序，过验证器
    pause_for_verification(page, secret, check_interval=5)
    click_tab_by_index(page, index=1, timeout=3000, debug=True, port=port)
    print(f"📌 切换卖出")
    # random_sleep(min_seconds=1, max_seconds=5)
    print()

    target_xpath = "//*[contains(@class, 'bn-flex') and contains(@class, 'text-TertiaryText') and contains(@class, 'items-center') and contains(@class, 'justify-between') and contains(@class, 'w-full')]//*[contains(@class, 'text-PrimaryText')]"
    raw_value = get_xpath_value_by_url(page, target_xpath, debug=True, port=port)
    print(raw_value)
    # 提取数字部分（支持小数）
    match = re.search(r'[\d,]+(?:\.\d+)?', raw_value)  # 提取数字部分（包含逗号和小数点）
    if match:
        value = float(match.group(0).replace(',', ''))  # 去掉逗号

    print(f"📌 获取到的币数：{value}")


    # 大于最小卖出数量，并且大于要保留的币，才进行卖出操作
    if (value > min_sell_amount) and (value > reserved_amount):


        price_xpath = '//*[@id="limitPrice"]'
        print(f"📌 输入卖价")

        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        fill_price_by_xpath(page, price_xpath, price=(float(buy_price) + buy_price_diff) * sell_price_percent,
                            debug=True, port=port)
        print()

        target_xpath = '//*[@id="limitAmount"]'
        print(f"📌 填写数量")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        fill_price_by_xpath(page, target_xpath, price=value - reserved_amount, debug=True, port=port)
        print()

        print("交易滚动条到底部")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        target_xpath = '//*[@id="__APP"]/div[2]/div[7]/div'
        scroll_target_page_human(page, xpath=target_xpath, direction="bottom", scroll_target="element", mode="fast",
                                 port=port)
        print()

        print(f"📌 取消反向订单")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        checkbox = toggle_checkbox(page,".bn-checkbox.bn-checkbox__square.data-size-md", should_check=False, interval=0.5,
                                   timeout=10,
                                   debug=True, port=port)

        if checkbox == False:
            refresh_url("复选框失败，刷新页面,跳过本次循环 ")
            return False

        print()

        print("滚动到页面底部")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        scroll_target_page_human(page, direction="bottom", scroll_target="page", mode="fast", port=port)
        print()

        # '//*[@id="__APP"]/div[2]/div[7]/div/div[2]/div[3]/button'
        button_xpath = "//*[contains(@class, 'bn-button') and contains(@class, 'bn-button__sell') and contains(@class, 'data-size-middle') and contains(@class, 'w-full')]"
        print(f"📌 点击卖出")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        click_button_by_xpath(page, button_xpath, timeout=3, interval=0.5, debug=True, port=port)
        print()

        # 卖单滑点没关系主要是为了成交买一
        try:
            #  监控谷歌验证器弹窗暂停程序，过验证器
            pause_for_verification(page, secret, check_interval=5)
            button_xpath = '/html/body/div[4]/div[2]/div/div/div[3]/button[1]'
            click_button_by_xpath(page, button_xpath, timeout=3, interval=0.5, debug=True, port=port)

            print(f"🚨 本次卖出交易确认")
        except Exception as e:
            print(f"🚨 没有下单手滑提醒")

        time.sleep(2)
        print("点击继续")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        # '//*[@id="__APP"]/div[2]/div[7]/div/div[2]/div[3]/button'
        button_xpath = '/html/body/div[4]/div[2]/div/div/button'
        click_button_by_xpath(page, button_xpath, timeout=3, interval=0.5, debug=True, port=port)

    else:

        print("滚动到页面底部")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        scroll_target_page_human(page, direction="bottom", scroll_target="page", mode="fast", port=port)
        print()

    return True

# 取消挂单，如果接在卖出之后，不要滚动到最后，如果不是需要往下滚动
def cancel_order(count):

    cnt = count
    print("取消未成交挂单")
    target_xpath = "//tbody[contains(@class, 'bn-web-table-tbody')]"

    # n = page.evaluate("""() => document.querySelectorAll('tbody.bn-web-table-tbody > tr[aria-rowindex]').length""")
    # print(f"未成交 ,订单数量{n}")
    # if n>0 :
        # 如果找到了元素，说明之前没成交，次数要减少一次

    # 向右拉动
    #  监控谷歌验证器弹窗暂停程序，过验证器
    pause_for_verification(page, secret, check_interval=5)
    scroll_target_page_human(page, xpath=target_xpath, direction="right", scroll_target="element", mode="fast",
                             port=port)

    # 取消按钮
    #  监控谷歌验证器弹窗暂停程序，过验证器
    pause_for_verification(page, secret, check_interval=5)
    button_xpath = '//*[@id="bn-tab-pane-orderOrder"]/div/div[3]/div/div/div[1]/table/thead/tr/th[9]/div'
    click_button_by_xpath(page, button_xpath, timeout=3, interval=0.5, debug=True, port=port)


    # 取消确认按钮
    #  监控谷歌验证器弹窗暂停程序，过验证器
    pause_for_verification(page, secret, check_interval=5)
    button_xpath = '/html/body/div[4]/div[2]/div/div/div[2]/button'
    is_click = click_button_by_xpath(page, button_xpath, timeout=3, interval=0.5, debug=True, port=port)

    if(is_click == True):
        print(f"取消 {1} 张订单")
        cnt = count - 1
        if cnt < 1:
            cnt = 1

    print()


    return cnt

if __name__ == "__main__":

    start_time = time.time()

    get_url_count = 0
    while True:


        get_url_count = get_url_count + 1
        # 使用
        print("当前页面 URL:", get_current_page_url(port)+"\n")
        target_url = get_current_page_url(port=port)

        if "devtools" in target_url:
            print("❌ URL 是 devtools , 重新获取")
            time.sleep(10)
        else:
            print("✅ URL 不包含 devtools , 成功获取页面")
            print()
            break

        if get_url_count >= 10:
            print("尝试十次未获取到网页，程序停止")
            exit()

    # 连接控制
    p, browser, page = init_browser(port=9222, target_url_contains=target_url)
    if not page:
        exit()
    page.set_default_timeout(5000)

    count = 0 # 统计第几笔交易
    repeat_times = 0 # 重复计数次数
    all_count = 0 # 循环次数
    previous_counter = None

    refresh_list = set()


    while True:

        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)

        _start_time = time.time()
        count = count+1
        all_count = all_count + 1
        # 判断是否重复
        if count == previous_counter:
            repeat_times += 1
        else:
            repeat_times = 1
            previous_counter = count

        print(f"【 第 {count} 笔交易 - 本交易循环次数 {repeat_times} - 执行循环 {all_count}  ==============】\n")


        # 每多少次
        if (all_count % refresh_interval == 0) :
            refresh_url("刷新页面")
            refresh_list.add(count)

        # 加载页面,判断是否加载完成
        load_webpage(page)
        print()


        # 执行卖出操作,如果页面不在最上面网页需要往上滚动
        is_execute_sell = execute_sell()
        # 卖出失败，跳过本次循环，并且计数器减去1
        if is_execute_sell == False:
            count = count - 1
            continue

        # 取消订单
        # 内部如有取消订单，次数减去1
        count = cancel_order(count)

        # 这里加入时间控制，处于此次时间内暂停程序
        # pause_if_in_off_periods(off_periods)

        print("滚动到页面顶部")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        scroll_target_page_human(page,direction="top",scroll_target="page",mode="fast" ,port=port)


        print("成交记录滚动到顶部")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        target_xpath = "//*[contains(@class, 'w-full') and contains(@class, 'h-full')]//*[@aria-label='grid']"
        scroll_target_page_human(page, xpath=target_xpath, direction="top", scroll_target="element",
                                 mode="fast",port=port)


        print(f"📌 切换买入")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        click_tab_by_index(page, index=0, timeout=3000, debug=True,port=port)


        # '//*[@id="__APP"]/div[2]/div[5]/div/div[2]/div/div[2]/div/div/div[1]/div[2]'
        target_xpath = "(//*[contains(@class, 'ReactVirtualized__Grid__innerScrollContainer')]//*[contains(@class, 'flex-1') and contains(@class, 'cursor-pointer')])[1]"
        buy_price = get_xpath_value_by_url(page, target_xpath, debug=True,port=port)
        print(f"📌 获取当前成交价：{buy_price}")

        target_xpath = "//*[contains(@class, 'bn-flex') and contains(@class, 'text-TertiaryText') and contains(@class, 'items-center') and contains(@class, 'justify-between') and contains(@class, 'w-full')]//*[contains(@class, 'text-PrimaryText')]"
        num = float(get_xpath_value_by_url(page, target_xpath, debug=True,port=port).split(" ")[0])
        print(f"📌 获取当前可用余额：{num}")

        print()
        if count == 1:
            save_balance_to_csv(num, username)


        print(f"📌 选择反向订单")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        checkbox = toggle_checkbox(page,".bn-checkbox.bn-checkbox__square.data-size-md", should_check=True, interval=0.5, timeout=10,
                        debug=True,port=port)


        if checkbox == False:
            #  监控谷歌验证器弹窗暂停程序，过验证器
            pause_for_verification(page, secret, check_interval=5)
            refresh_url("复选框失败，刷新页面,跳过本次循环 ")
            count = count - 1
            continue

        print()

        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        target_xpath = '//*[@id="limitPrice"]'
        # //*[contains(@class, 'w-full')]//*[contains(@class, 'bn-textField') and contains(@class, 'bn-textField__line')]
        print(f"📌 输入买价")
        fill_price_by_xpath(page, target_xpath, price=float(buy_price) + buy_price_diff, debug=True, port=port)
        print()

        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        target_xpath = "//input[@id='limitTotal' and contains(@class, 'bn-textField-input') and contains(@placeholder, '最小')]"
        print(f"📌 输入成交额")
        fill_price_by_xpath(page, target_xpath, price=cost, debug=True,port=port)

        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        target_xpath = "//input[@id='limitTotal' and contains(@class, 'bn-textField-input') and contains(@placeholder, '卖出')]"
        print(f"📌 输入卖出价")
        fill_price_by_xpath(page, target_xpath, price= (float(buy_price)) * sell_price_percent, debug=True,port=port)
        print()

        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        print("交易滚动条到底部")
        target_xpath = '//*[@id="__APP"]/div[2]/div[7]/div'
        scroll_target_page_human(page, xpath=target_xpath, direction="bottom", scroll_target="element",
                                 mode="fast",port=port)
        print()


        print("滚动到页面底部")
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        scroll_target_page_human(page, direction="bottom", scroll_target="page", mode="fast",port=port)
        print()


        print("点击购买")
        # '//*[@id="__APP"]/div[2]/div[7]/div/div[2]/div[3]/button'
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        button_xpath = "//*[contains(@class, 'bn-button') and contains(@class, 'bn-button__buy') and contains(@class, 'data-size-middle')]"
        click_button_by_xpath(page, button_xpath, timeout=10, interval=0.5, debug=True,port=port)
        print()


        try:

            print("如果弹出滑点提醒，点击取消")
            #  监控谷歌验证器弹窗暂停程序，过验证器
            pause_for_verification(page, secret, check_interval=5)
            button_xpath = '/html/body/div[4]/div[2]/div/div/div[3]/button[2]'
            if(click_button_by_xpath(page, button_xpath, timeout=3, interval=0.5, debug=True,port=port)):
                count = count - 1
                print(f"🚨 本次交易取消")
                continue

        except Exception as e:
            print(f"🚨 买单没有下单手滑提醒")

        # 单击确认
        print("确认购买")
        button_xpath = '/html/body/div[4]/div[2]/div/div/button'
        #  监控谷歌验证器弹窗暂停程序，过验证器
        pause_for_verification(page, secret, check_interval=5)
        click_button_by_xpath(page, button_xpath, timeout=3, interval=0.5, debug=True,port=port)

        # 最后一次执行结束任务
        if count == total_runs:

            print("休息60s,取消未成交订单，结束本次任务")
            time.sleep(60)

            print("滚动到页面底部")
            #  监控谷歌验证器弹窗暂停程序，过验证器
            pause_for_verification(page, secret, check_interval=5)
            scroll_target_page_human(page, direction="bottom", scroll_target="page", mode="fast",port=port)
            print()

            # 取消未成交挂单
            cancel_order(count)
            print()

            print("滚动到页面顶部")
            #  监控谷歌验证器弹窗暂停程序，过验证器
            pause_for_verification(page, secret, check_interval=5)
            scroll_target_page_human(page, direction="up", scroll_target="page", mode="fast", port=port)
            print()

            print("检查仓位确认卖出")
            # 提取数字部分（支持小数）
            execute_sell()
            print()
            time.sleep(5)

            print(f"📌 切换买入")
            #  监控谷歌验证器弹窗暂停程序，过验证器
            pause_for_verification(page, secret, check_interval=5)
            click_tab_by_index(page, index=0, timeout=3000, debug=True, port=port)
            print()


            target_xpath = "//*[contains(@class, 'bn-flex') and contains(@class, 'text-TertiaryText') and contains(@class, 'items-center') and contains(@class, 'justify-between') and contains(@class, 'w-full')]//*[contains(@class, 'text-PrimaryText')]"
            num = float(get_xpath_value_by_url(page, target_xpath, debug=True, port=port).split(" ")[0])
            print(f"📌 获取当前可用余额：{num}")

            print()
            # 保存文件
            save_balance_to_csv(num, username)
            # 计算用时
            elapsed_time(start_time,"总运行时间")
            print()

            break

        print()
        # 计算用时
        elapsed_time(_start_time, "本次运行时间")
        elapsed_time(start_time,"总运行时间")
        random_sleep(min_interval, max_interval)
        print()