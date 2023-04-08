import asyncio
import datetime
import json
import logging
import os
import re
import time
from urllib import parse

from cacheout import FIFOCache
from telethon import TelegramClient, events

# 0. SSH进入docker容器
# 0. docker exec -it qinglong bash
# 1. pip3 install -U cacheout
# 2. 复制magic.py,magic.json到/ql/config/目录 并配置
# 3. python3 /ql/config/magic.py 用手机号登录
# 4. 给bot/自建群发送magic 有反应即可
# 5. 先执行停止容器命令：pm2 stop magic  在执行后台运行命令：pm2 start /ql/config/magic.py -x --interpreter python3
# 6. 挂起bot到后台 查看状态 pm2 l
# 7. 如果修改了magic.json,执行pm2 restart magic 即可重启
# 8. 遇到database is locked的问题 容器内执行pm2  stop magic  然后执行 pm2 start magic 或者 pm2 start /ql/config/magic.py -x --interpreter python3
# 9. 在配置文件最后新增变量： 文件最后 手动加一行    #Magic线报变量区域     就可以实现了，如果没有就是文件开头添加变量
# 10. 重启容器：发送magic 重启/magic cq

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.INFO)
# 创建
logger = logging.getLogger("magic")
logger.setLevel(logging.INFO)

_ConfigCar = ""
_ConfigSh = ""
_mblx=""
if os.path.exists("/jd/config/magic.json"):
    _ConfigCar = "/jd/config/magic.json"
    _ConfigSh = "/jd/config/config.sh"
    _mblx = "Helloworld"
elif os.path.exists("/ql/config/magic.json"):
    _ConfigCar = "/ql/config/magic.json"
    _ConfigSh = "/ql/config/config.sh"
    _mblx = "qinglong"
elif os.path.exists("/ql/data/config/magic.json"):
    _ConfigCar = "/ql/data/config/magic.json"
    _ConfigSh = "/ql/data/config/config.sh"
    _mblx = "qinglong"
else:
    logger.info("未找到magic.json config.sh")

with open(_ConfigCar, 'r', encoding='utf-8') as f:
    magic_json = f.read()
    properties = json.loads(magic_json)

# 缓存
cache = FIFOCache(maxsize=properties.get("monitor_cache_size"), ttl=0, timer=time.time)
cacheRun = FIFOCache(maxsize=properties.get("monitor_cache_size"), ttl=0, timer=time.time)

# Telegram相关
api_id = properties.get("api_id")
api_hash = properties.get("api_hash")
bot_id = properties.get("bot_id")
bot_token = properties.get("bot_token")
user_id = properties.get("user_id")
# 监控相关
log_path = properties.get("log_path")
log_send = properties.get("log_send", True)
log_send_id = properties.get("log_send_id")
monitor_cars = properties.get("monitor_cars")
#logger.info(f"监控的频道或群组-->{monitor_cars}")
monitor_converters = properties.get("monitor_converters")
#logger.info(f"监控转换器-->{monitor_converters}")
monitor_converters_whitelist_keywords = properties.get("monitor_converters_whitelist_keywords")
#logger.info(f"不转换白名单关键字-->{monitor_converters_whitelist_keywords}")
monitor_black_keywords = properties.get("monitor_black_keywords")
#logger.info(f"黑名单关键字-->{monitor_black_keywords}")
monitor_scripts = properties.get("monitor_scripts")
monitor_auto_stops = properties.get("monitor_auto_stops")
#logger.info(f"监控的自动停车-->{monitor_auto_stops}")
rules = properties.get("rules")
#logger.info(f"监控的自动解析-->{monitor_auto_stops}")
export_expression = r'([\s\S]*?)export\s?\w*=(".*?"|\'.*?\')([\s\S]*)'
#logger.info(f"export监控匹配条件-->{export_expression}")
URL_expression = r'http[s]{0,1}?://(?:[#?&\-=\w./]|(?:%[\da-fA-F]+))+'
#logger.info(f"URL信息监控匹配条件-->{url_expression}")
JCommand_expression = r'[㬌京亰倞兢婛景椋猄竞竟競竸綡鲸鶁][一-龥]{8,16}[东倲冻凍埬岽崠崬東栋棟涷菄諌鯟鶇]|[$%￥@！(#!][a-zA-Z0-9]{6,20}[$%￥@！)#!]'
#logger.info(f"JCommand信息监控匹配条件-->{JCommand_expression}")
combined_pattern = f'{export_expression}|{URL_expression}|{JCommand_expression}'
#logger.info(f"最终群组信息监控匹配条件-->{combined_pattern}")

if properties.get("proxy"):
    if properties.get("proxy_type") == "MTProxy":
        proxy = {
            'addr': properties.get("proxy_addr"),
            'port': properties.get("proxy_port"),
            'proxy_secret': properties.get('proxy_secret', "")
        }
    else:
        proxy = {
            'proxy_type': properties.get("proxy_type"),
            'addr': properties.get("proxy_addr"),
            'port': properties.get("proxy_port"),
            'username': properties.get('proxy_username', ""),
            'password': properties.get('proxy_password', "")
        }
    client = TelegramClient("magic", api_id, api_hash, proxy=proxy, auto_reconnect=True, retry_delay=1, connection_retries=99999).start()
else:
    client = TelegramClient("magic", api_id, api_hash, auto_reconnect=True, retry_delay=1, connection_retries=99999).start()


def rest_of_day():
    """
    :return: 截止到目前当日剩余时间
    """
    today = datetime.datetime.strptime(str(datetime.date.today()), "%Y-%m-%d")
    tomorrow = today + datetime.timedelta(days=1)
    nowTime = datetime.datetime.now()
    return (tomorrow - nowTime).seconds - 90  # 获取秒


def rwcon(arg):
    if arg == "str":
        with open(_ConfigSh, 'r', encoding='utf-8') as f1:
            configs = f1.read()
        return configs
    elif arg == "list":
        with open(_ConfigSh, 'r', encoding='utf-8') as f1:
            configs = f1.readlines()
        return configs
    elif isinstance(arg, str):
        with open(_ConfigSh, 'w', encoding='utf-8') as f1:
            f1.write(arg)
    elif isinstance(arg, list):
        with open(_ConfigSh, 'w', encoding='utf-8') as f1:
            f1.write("".join(arg))


async def export(text):
    messages = text.split("\n")
    change = ""
    key = ""

    for message in messages:
        if "export " not in message:
            continue
        kv = message.replace("export ", "")
        key = kv.split("=")[0]
        action = monitor_scripts.get(key)
        name = action.get("name")

        value = re.findall(r'"([^"]*)"', kv)[0]
        configs = rwcon("str")
        if kv in configs:
            continue
        if key in configs:
            configs = re.sub(f'{key}=("|\').*("|\')', kv, configs)
            change += f"\n【执行替换】环境变量成功\n{kv}"
            #await client.send_message(bot_id, change)
        else:
            end_line = 0
            configs = rwcon("list")
            for config in configs:
                if "Magic线报变量区域" in config:
                    end_line = configs.index(config)
                    end_line += 3
                    break
            configs.insert(end_line, f'\n#{name}\nexport {key}="{value}"\n')
            change += f"\n【执行新增】环境变量成功\n{kv}"
            #await client.send_message(bot_id, change)
        rwcon(configs)
    if len(change) == 0:
        logger.info(f'【取消替换】变量无需修改')
        #await client.send_message(bot_id, f'【取消替换】变量无需修改\n{kv}')

# 发送消息的用户是user_id时候，当发送没水了会模糊关联停止 monitor_auto_stops名单内的脚本
@client.on(events.NewMessage(from_users=[user_id], pattern='^没水了$'))
async def handler(event):
    for auto_stop_file in monitor_auto_stops:
        os.popen(f"ps -ef | grep {auto_stop_file}" + " | grep -v grep | awk '{print $1}' | xargs kill -9")
    str = 'Magic监控发现【%s】没水，执行脚本终止操作' % (auto_stop_file)
    str = str + "\n\n【本条信息将在20秒钟后自动删除】"
    await event.edit(str)        
    await asyncio.sleep(20)
    await event.delete()



# 设置变量
@client.on(events.NewMessage(from_users=[user_id], pattern='^(magic 重启|magic cq)$'))
async def handler(event):
    rebootTxt = "Magic监控开始重启... ...\n\n【本条信息将在2秒钟后自动删除】"
    await event.edit(rebootTxt)        
    await asyncio.sleep(2)
    await event.delete()
    os.system('pm2 restart magic')


# 设置变量
@client.on(events.NewMessage(from_users=[user_id], pattern='^(magic 清理|magic 清空|magic qk|magic ql)$'))
async def handler(event):
    b_size = cache.size()
    #logger.info(f"清理前缓存数量，{b_size}")
    cache.clear()
    a_size = cache.size()
    #logger.info(f"清理后缓存数量，{a_size}")
    if b_size > 0:
        str = 'Magic监控【%s】个记录缓存(包含正在排队)被重置归【%s】' % (b_size,a_size)
        str = str + "\n\n【本条信息将在10秒钟后自动删除】"
    else:
        str = '崽崽 你的监控缓存历史记录空空如也，被抛弃了吧  替你哭一会！！'
        str = str + "\n\n【本条信息将在10秒钟后自动删除】"
    await event.edit(str)
    await asyncio.sleep(10)
    await event.delete()
    #await client.send_message(bot_id, f'Magic监控清理缓存结束 {b_size}-->{a_size}')


# 设置变量
@client.on(events.NewMessage(from_users=[user_id], pattern='^magic$'))
async def handler(event):
    try:
        waitQueueTxt = "Magic监控运行中... ..."
        waitQueueTxt0 = ""
        waitQueueTxt1 = ""
        waitQueueNumTotal = 0
        for key in monitor_scripts:
            action = monitor_scripts[key]
            name = action.get('name')
            queue_name = action.get("queue_name")
            curr_queue = queues[queue_name]
            waitQueueNum = curr_queue.qsize()            
            if queues.get(queue_name) is not None:
                if not action.get("enable"):
                    continue  #关闭监控的不显示
                else:
                    if waitQueueNum > 0: #只显示有队列的任务
                        waitQueueNumTotal = waitQueueNumTotal + waitQueueNum
                        str = '\n%s---> 当前排队 %s😊' % (name,waitQueueNum)
                        waitQueueTxt1 = waitQueueTxt1 + str
                    else: #只显示有队列的任务
                        str = '\n%s' % (name)
                        waitQueueTxt0 = waitQueueTxt0 + str
                continue
        cacheRun_size = cacheRun.size()
        if(not waitQueueTxt1):
            #waitQueueTxt = waitQueueTxt0 + "\n---------------------⬇⬇【正在排队任务】⬇⬇---------------------\n" + "\n\n【本次监控启动以来总运行线报】 "+ f'{cacheRun_size}' + "\n\n【本条信息将在10秒钟后自动删除】"
            waitQueueTxt = "\n⬇⬇【正在排队任务】⬇⬇" + "\n\n【本次监控启动以来总运行线报】 "+ f'{cacheRun_size}' + "\n\n【本条信息将在10秒钟后自动删除】"
        else:
            #waitQueueTxt = waitQueueTxt0 + "\n---------------------⬇⬇【正在排队任务】⬇⬇---------------------\n" + waitQueueTxt1 + "\n\n【当前总排队】 " + f'{waitQueueNumTotal}' + "\n【本次监控启动以来总运行线报】 "+ f'{cacheRun_size}'  + "\n\n【本条信息将在10秒钟后自动删除】"
            waitQueueTxt = "\n⬇⬇【正在排队任务】⬇⬇\n" + waitQueueTxt1 + "\n\n【当前总排队】 " + f'{waitQueueNumTotal}' + "\n【本次监控启动以来总运行线报】 "+ f'{cacheRun_size}'  + "\n\n【本条信息将在10秒钟后自动删除】"
        await event.edit(waitQueueTxt)        
        await asyncio.sleep(10)
        await event.delete()
    except Exception as e:
        logger.error(e)



# 提取多行转换
async def converter_lines(text):
    before_eps = text.split("\n")
    after_eps = [elem for elem in before_eps if elem.startswith("export")]
    return await converter_handler("\n".join(after_eps))

async def get_activity_info(text):
    result = re.findall(r'((http|https)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|])', text)
    logger.info(result)
    if len(result) <= 0:
        return None, None
    url = re.search('((http|https)://[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|])', text)[0]
    logger.info(url)
    params = parse.parse_qs(parse.urlparse(url).query)
    logger.info(params)
    ban_rule_list = [
        'activityId',
        'shopId',
        'giftId',
        'actId',
        'tplId',
        'token',
        'code',
        'a',
        'id']
    activity_id = ''
    for key in ban_rule_list:
        activity_id = params.get(key)
        #logger.info(activity_id)
        if activity_id is not None:
            activity_id = params.get(key)
            activity_id = activity_id[0]
            break
    return activity_id, url
    
async def converter_handler(text):
    text = "\n".join(list(filter(lambda x: "export " in x, text.replace("`", "").split("\n"))))
    for c_w_key in monitor_converters_whitelist_keywords:
        result = re.search(c_w_key, text)
        if result is not None:
            return text
    try:
        tmp_text = text
        # 转换
        for c_key in monitor_converters:
            result = re.search(c_key, tmp_text)
            if result is None:
                #logger.info(f"规则不匹配 {c_key},下一个")
                continue
            rule = monitor_converters.get(c_key)
            target = rule.get("env")
            argv_len = len(re.findall("%s", target))
            values = re.findall(r'"([^"]*)"', tmp_text)
            if argv_len == 1:
                target = target % (values[0])
            elif argv_len == 2:
                activity_id, url = await get_activity_info(tmp_text)
                target = target % (activity_id, url)
                #logger.info(f"两个变量组合{target}")
            elif argv_len == 3:
                target = target % (values[0], values[1], values[2])
                logger.info(f"三个变量组合{target}")
            else:
                print("不支持更多参数")
            tmp_text = target
            #await client.send_message(bot_id, f'转换数据-----\n{tmp_text}')
            break
        text = tmp_text.split("\n")[0]
    except Exception as e:
        logger.info(str(e))
    return text


queues = {}

async def task(task_name, task_key):
    #logger.info(f"队列监听--> {task_name} {task_key} 已启动，等待任务")
    curr_queue = queues[task_key]
    while True:
        try:
            param = await curr_queue.get()
            groupname = param.get("groupname")
            logger.info(f"出队执行 {param}")
            exec_action = param.get("action")
            actionname = exec_action.get("name")
            text = param.get("text")
            kv = text.replace("export ", "")
            activity_id, url = await get_activity_info(text) #重新获取id url
            if activity_id is None:
                key = kv.split("=")[0]
                activityid = kv.split("=")[1] #取id格式变量值  #activityid为空的情况下判断url是否为空，如果url是none，说明该变量是个id形式变量，直接取id值
                activity_id = activityid.replace('"','') #去除双引号
            # 默认立马执行
            #await client.send_message(bot_id, f'【{groupname}】\n🎥{actionname}当前无需排队等待，立即执行\n{kv}')
            #await export(text)
            #await cmd(exec_action.get("task", ""))
            waitQueueNum = curr_queue.qsize() 
            if waitQueueNum > 0:
                #exec_action = param.get("action")
                await client.send_message(bot_id, f'【{groupname}】\n🎥{actionname}出队执行，剩余排队【{waitQueueNum}】，当前线报活动结束延迟 【 {exec_action["wait"]} 】 秒执行下一个\n{kv}')
                cacheRun.set(activity_id, activity_id, rest_of_day())
                await export(text)
                await cmd(exec_action.get("task", ""))
                await asyncio.sleep(exec_action['wait'])
                #await client.send_message(bot_id, f'🎥{actionname}\n排队长度{waitQueueNum}，活动切换预设间隔{exec_action["wait"]}秒执行')
            else:
                # 默认立马执行
                await client.send_message(bot_id, f'【{groupname}】\n🎥{actionname}当前无排队立即出队执行\n{kv}')
                cacheRun.set(activity_id, activity_id, rest_of_day())
                await export(text)
                await cmd(exec_action.get("task", ""))
        except Exception as e:
            logger.error(e)
            await client.send_message(bot_id, f'抱歉，遇到未知错误！\n{str(e)}')


async def cmd(exec_cmd):
    try:
        #logger.info(f'执行命令 {exec_cmd}')
        name = re.findall(r'(?:.*/)*([^. ]+)\.(?:js|py|sh)', exec_cmd)[0]
        tmp_log = f'{log_path}/{name}.{datetime.datetime.now().strftime("%H%M%S%f")}.log'
        #logger.info(f'日志文件 {tmp_log}')
        proc = await asyncio.create_subprocess_shell(
            f"{exec_cmd} >> {tmp_log} 2>&1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if log_send:
            await client.send_file(log_send_id, tmp_log)
            os.remove(tmp_log)
    except Exception as e:
        #logger.error(e)
        await client.send_message(bot_id, f'抱歉，遇到未知错误！\n{str(e)}')

async def check_export(exports):
    """
    根据export匹配变量处理
    :param export:
    :return:
    """
    result = None
    export_dict = {e[0]: e[1] for e in exports}
    #if len(export_dict) == 2:
        # 完善信息有礼Kr变量处理
        #if "jd_completeInfoActivity_activityId" in export_dict and "jd_completeInfoActivity_venderId" in export_dict:
        #    activity_id = export_dict["jd_completeInfoActivity_activityId"]
        #    vender_id = export_dict["jd_completeInfoActivity_venderId"]
        #    result = 'export jd_wxCompleteInfoId="' + str(activity_id) + '&' + str(vender_id) + '"'
    
    return result
    
@client.on(events.NewMessage(chats=monitor_cars, pattern=combined_pattern))
async def handler(event):
    message_text = event.message.text
    try:
        groupname = f'[{event.chat.title}](https://t.me/c/{event.chat.id}/{event.message.id})'
    except Exception:
        groupname = "我的机器人Bot"
        pass

    if re.search(JCommand_expression, message_text):
        print("Matched JCommand_expression")
        return
    elif re.search(URL_expression, message_text):
        print("Matched URL_expression")
        return
    elif re.search(export_expression, message_text):
        await converter_handler(message_text)
    else:
        return
