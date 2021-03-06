import requests
import threading
import re
import json
import os
import time
from lxml import etree
from queue import Queue
import subprocess
from tqdm import tqdm

headers = {
    'Connection':
    'keep-alive',
    'Referer':
    'https://www.bilibili.com/',
    "user-agent":
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 \
    (KHTML, like Gecko) Chrome/85.0.4183.102 \
    YaBrowser/20.9.3.189 (beta) Yowser/2.5 Safari/537.36'
}

video_queue = Queue(300)


def single_data(url):
    resp = requests.get(url, headers=headers)
    html = etree.HTML(resp.text)
    title = html.xpath('//div[@id="viewbox_report"]/h1/@title')[0]
    print('下载：', title)
    data = re.search(r'__playinfo__=(.*?)</script><script>',
                     resp.text).group(1)
    data = json.loads(data)
    ptitle = re.search(
        r'\<script\>window\.__INITIAL_STATE__=(.*?);\(function\(\)',
        resp.text).group(1)
    ptdata = json.loads(ptitle)
    if 'p=' in url:
        p = int(url.split('=')[-1])
        ptitle = str(p) + ptdata['videoData']['pages'][p - 1]['part']
    else:
        ptitle = title
    try:
        time = data['data']['dash']['duration']
        minute = int(time) // 60
        second = int(time) % 60
        video_url = data['data']['dash']['video'][0]['baseUrl']
        audio_url = data['data']['dash']['audio'][0]['baseUrl']
        video_queue.put([video_url, audio_url, ptitle])
    except KeyError:
        time = data['data']['timelength'] // 1000  # 我发现其实有些小视频的格式是不一样的，，，
        minute = int(time) // 60  # 这种就是一个视频，不用合并音频，，视频啥的了。。
        second = int(time) % 60
        video_url = data['data']['durl'][0]['url']
        video_queue.put([video_url, ptitle])
    print('视频时长{}分{}秒'.format(minute, second))


# 定义下载函数(调用video_audio_merge合并生成的 音频+视频 文件)
def download():
    while not video_queue.empty():
        data = video_queue.get()
        if len(data) == 3:
            # print('%s   开始下载' % data[2])
            data[2] = re.sub(r'[\\/:\*\?<>\|"]', '', data[2])
            for i in range(2):
                resp = requests.get(data[i], stream=True, headers=headers)
                content_size = int(resp.headers['content-length'])
                data[2] = re.sub(r'[\\/:\*\?<>\|"]', '', data[2])
                if i==0:
                    file_name = '%s_video.mp4' % data[2]
                else:
                    file_name = '%s_audio.mp4' % data[2]
                if os.path.exists(file_name):
                    first_byte = os.path.getsize(file_name)
                else:
                    first_byte = 0
                if first_byte >= content_size:
                    return content_size
                progressbar = tqdm(
                    total=content_size, initial=first_byte,
                    unit='B', unit_scale=True,
                    desc='......%s 下载进度'%file_name[-15:])
                with open(file_name, 'ab') as f:
                    for chunk in resp.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            progressbar.update(1024)
                progressbar.close()
                
            video_audio_merge(data[2])
        else:
            data[1] = re.sub(r'[\\/:\*\?<>\|"]', '', data[1])
            with open('%s_video.mp4' % data[1], 'wb') as f:  # 只有视频部分
                resp = requests.get(data[0], headers=headers)
                f.write(resp.content)
                print('%s下载完成' % data[1])


# 定义将视频和音频合并的函数(需要调用ffmpeg程序)
def video_audio_merge(video_name):
    print("视频合成开始：%s" % video_name)
    command = 'ffmpeg -i "%s_video.mp4" -i \
        "%s_audio.mp4" -c copy "%s.mp4" -y \
            -loglevel quiet' % (
        video_name, video_name, video_name)
    vamerge = subprocess.Popen(command, shell=True)
    vamerge.wait()
    print("视频合成结束：%s" % video_name)


# 定义主函数
def main():
    url = input('''输入下载链接（例如：https://www.bilibili.com/video/av91748877?p=1,
    https://www.bilibili.com/video/av91748877?p=2)多视频请用英文逗号分隔:\n'''
                )
    urls = url.split(',')
    for each in urls:
        single_data(each)  # 调用single_data函数
        time.sleep(1)
    for x in range(3):
        th = threading.Thread(
            target=download)  # 调用download函数(进一步调用video_audio_merge子程序)
        th.start()


if __name__ == '__main__':
    main()
