# -*- coding: utf-8 -*-

from appium import webdriver
import time
import ssim
import os
import datetime
import base64
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s:%(levelname)s: %(message)s"
)

# Appium 服务地址
EXECUTOR = 'http://127.0.0.1:4723/wd/hub'

# Appium 所需的被测手机参数，需要根据实际情况修改 platformVersion、deviceName
ANDROID_CAPS = {
    'platformName': 'Android',
    'automationName': 'UIAutomator2',
    'appPackage': 'com.tencent.mm',
    'appActivity': '.ui.LauncherUI',
    'fullReset': False,
    'noReset': True,
    'newCommandTimeout': 120,
    'platformVersion': '7.0',
    'deviceName': '0915f911a8d02504',
}

# Appium 查找一个元素的最大等待时间
IMPLICITLY_WAIT = 10

# 被测小程序名
WXAPP = "有车以后"

# 视频被切割的帧数，即1秒切割成多少张图片
FPS = 50

# 项目路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def calculate_boot_time(pngs_dir, fps, refer_end_pic):
    """
    通过一系列的截图文件，计算出启动时间
    :param pngs_dir: 截图所在目录
    :param fps: 帧数
    :param refer_end_pic: 结束位置参考图片
    :return: 启动时间
    """
    # 找启动的开始（点击响应）、结束时间（渲染首页内容）点
    pngs = os.listdir(pngs_dir)
    pngs.sort()
    start_t, end_t, boot_time = 0, 0, 0

    # 找开始点，对比和第一张图的相似度
    refer_start_pic = os.path.join(pngs_dir, pngs[0])
    for png in pngs[1:]:
        dest_png = os.path.join(pngs_dir, png)
        factor = ssim.compute_ssim(refer_start_pic, dest_png)
        logging.info("%s 相似度：%f" % (png, factor))
        if factor < 0.9:
            start_t = int(png.split('.png')[0])
            break

    if start_t > 0:
        # 继续找结束点，和灰度的连续匹配两次的最后位置
        third_f, second_f, first_f = 0, 0, 0
        for png in pngs[start_t:]:
            dest_png = os.path.join(pngs_dir, png)
            current_f = ssim.compute_ssim(refer_end_pic, dest_png)
            logging.info("%s 相似度：%f" % (png, current_f))
            third_f = second_f
            second_f = first_f
            first_f = current_f
            if third_f > 0.97 and second_f > 0.97 and first_f < 0.97:
                end_t = int(png.split('.png')[0])
                break

    # 有效性判断和时间计算
    if start_t == 0 or end_t == 0:
        logging.warning("没有找到开始或者结束图片")
    elif end_t == len(pngs):
        logging.warning("结束位置错误")
    else:
        boot_time = int((end_t - start_t) * 1000 / fps)
    return boot_time


def test_boot_time():
    """
    小程序启动时间的度量，点击后录屏，然后把视频切割成图片帧，最后通过图片分析计算
    本项目仅做demo参考，未做完善的异常处理
    :param driver:
    :param cmdopt:
    :return:
    """
    # 初始化 Appium 的 driver 对象
    driver = webdriver.Remote(EXECUTOR, ANDROID_CAPS)
    driver.implicitly_wait(IMPLICITLY_WAIT)

    # 进入下拉栏目，被测小程序需要出现在下拉栏里，建议收藏起来，以备日后持续测试
    width, height = driver.get_window_size()['width'], driver.get_window_size()['height']
    driver.swipe(width * 0.5, height * 0.25, width * 0.5, height * 0.75, duration=800)
    time.sleep(2)

    # 本地保存目录，按天划分，一个场景可以有多个记录
    mp4_dir = os.path.join(BASE_DIR, 'data', '{:%Y-%m-%d}'.format(datetime.datetime.now()), WXAPP,
                           '{:%H%M%S}'.format(datetime.datetime.now()))
    pngs_dir = os.path.join(mp4_dir, 'pngs')

    os.makedirs(pngs_dir, exist_ok=True)

    mp4 = os.path.join(mp4_dir, 'rec.mp4')
    png = os.path.join(pngs_dir, '%04d.png')

    # 录制屏幕
    driver.start_recording_screen()

    # 这里通过 xpath 定位小程序，放置命中其他版本，例如开发版、体验版
    xpath = "//android.widget.TextView[@text='%s']/../android.widget.FrameLayout[not(android.widget.TextView)]" \
          % WXAPP
    driver.find_element_by_xpath(xpath).click()
    time.sleep(12)

    mp4_base64 = driver.stop_recording_screen()

    # 生成视频文件
    open(mp4, 'wb').write(base64.b64decode(mp4_base64))
    os.system('ffmpeg -i %s -r %d -ss 00:00:01 -t 00:00:10 -s 1080x1920 %s' % (mp4, FPS, png))

    # 找启动的开始（点击屏幕）、结束时间（渲染首页内容）点
    refer_end_pic = os.path.join(BASE_DIR, 'reference', WXAPP, 'end.png')
    boot_time = calculate_boot_time(pngs_dir, FPS, refer_end_pic=refer_end_pic)
    if boot_time > 0:
        # TODO 把这个时间上传到服务器上，进行数据统计和报表制作
        return boot_time
    else:
        raise ValueError
