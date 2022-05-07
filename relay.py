#!/bin/python
import requests, argparse, threading, time, json, os
from subprocess import Popen

version = "0.0.3"
title = f"Relay v{version}"

def updateScr(postCount):
    os.system('cls' if os.name == 'nt' else 'clear')
    print(title)
    print(f"Post counter: {postCount}")

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", default="config.json")
parser.add_argument("-nc", "--no-cache", action="store_true")
args = parser.parse_args()

if args.config[:4]=="url:":
    config = json.loads(requests.get(args.config[4:]).text)
else:
    config = json.load(open(args.config))

history = {"ids": [False]}
if not args.no_cache:
    try:
        history = json.load(open("cache.json"))
    except FileNotFoundError:
        pass    
#https://oauth.vk.com/authorize?client_id=[APP ID]&display=page&scope=wall,groups,offline&response_type=token&v=5.131&state=123456

def updater_maker(filename, fileurl, executable):
    string = f"from subprocess import Popen\nimport requests\nf = open('{filename}', 'w')\nf.write(requests.get('{fileurl}').text)\nf.close()\n"
    if executable: string = string + f"Popen('python {filename}', shell=True)\nexit()"
    f = open("updater.py", "w")
    f.write(string)
    f.close()
    Popen("python updater.py", shell=True)
    telegramApi("sendMessage", {"chat_id": config['telegram']['user_id'], "text": "Updated!"})


def telegramApi(method, payload): return requests.get(f"https://api.telegram.org/bot{config['telegram']['token']}/{method}", params=payload).json()

def get_updates(config):
    result = telegramApi("getUpdates", {})
    if result['ok']==True:
        return result["result"]
    else:
        return [{"update_id": 0}]

def replier(config):
    update_id = get_updates(config)[-1]['update_id']
    while True:
        messages = get_updates(config)
        for message in messages:
            if update_id<message['update_id']:
                update_id=message['update_id']
                if "text" in message["message"].keys():
                    text = message["message"]["text"]
                else:
                    text = "/update"
                payload = {"chat_id": config['telegram']['user_id'], "text": "Invalid command!"}
                if text=="/help":
                    payload["text"] = "/online - check if bot is online\n/update - config files update"
                elif text=="/online":
                    payload["text"] = "yes"
                elif text=="/update":
                    if "document" in message["message"]:
                        filepath = telegramApi("getFile", {"file_id": message["message"]["document"]["file_id"]})["result"]["file_path"]
                        filename = message["message"]["document"]["file_name"]
                        updater_maker(filename, "https://api.telegram.org/file/bot{config['telegram']['token']}/{filepath}", False)
                        if args.config[:4]!="url:" and filename[-4:]=="json": config = json.load(open(filename))
                if text!="/update": telegramApi("sendMessage", payload)

replierThread = threading.Thread(target=replier, args=(config,))
replierThread.daemon = True
replierThread.start()

postCount = 0
while 1:
    # update check
    remote_version = requests.get("https://api.github.com/repos/mrtnvgr/relay/releases/latest").json()
    if "name" not in remote_version.keys(): remote_version = version
    if version!=remote_version:
        updater_maker("relay.py", "https://raw.githubusercontent.com/mrtnvgr/relay/main/relay.py", True)
        exit(0)
    updateScr(postCount)
    newPosts = []
    payload = {"access_token": config["vk"]["token"],
               "domain": "doujinmusic",
               "offset": "1",
               "count": config["maxHistory"],
               "sort": "desc",
               "v": "5.131"}
    posts = requests.get("https://api.vk.com/method/wall.get", params=payload).json()
    if 'error' in posts.keys():
        print("VK api error!")
        print(posts)
        exit(1)
    else:
        posts = posts["response"]["items"]
    for i in posts:
        if i['id'] not in history["ids"] or history["ids"][0]==False:
            whitelist = False
            blacklist = False
            for tag in config["whitelist"]:
                if tag in i["text"]: whitelist = True
            for tag in config["blacklist"]:
                if tag in i["text"]: blacklist = True
            if (whitelist and not blacklist and config["postType"]["albums"]) or ("#статьи@doujinmusic" in i["text"] and config["postType"]["articles"]) or "@doujinmusic" not in i["text"]:
                newPosts.append(i)
    if len(newPosts)>0:
        for post in newPosts:
            history["ids"].append(post['id'])
            if history["ids"][0]==False: history["ids"].pop(0)
            if len(history["ids"])>config["maxHistory"]: history["ids"] = history["ids"][-config["maxHistory"]:]
            if not args.no_cache: json.dump(history, open("cache.json", "w"))
            file = [False, False]
            if "attachments" in post:
                for attachment in post["attachments"]:
                    if attachment["type"]=="doc":
                        filetype = attachment["doc"]["title"][:6]
                        if filetype=="[FLAC]" or "[WAV]" in filetype:
                            file = [True, attachment["doc"]]
                        else:
                            if file[0]==False:
                                file[1] = attachment["doc"]
                    elif attachment["type"]=="photo":
                        postPhoto = attachment["photo"]["sizes"][-1]["url"]
                    elif attachment["type"]=="link" and "#статьи@doujinmusic" in post['text']:
                        file = [True, attachment["link"]]
                        postPhoto = attachment["link"]["photo"]["sizes"][-1]["url"]
                        break
                if file[1]!=False:
                    payload = {"chat_id": config['telegram']['user_id'],
                               "photo": postPhoto,
                               "caption": f"{post['text']} <a href='vk.com/wall{post['from_id']}_{post['id']}'>(link)</a>\n\n<a href='{file[1]['url']}'>{file[1]['title']}</a>",
                               "parse_mode": "HTML"}
                    telegramApi("sendPhoto", payload)
                    postCount += 1
                else:
                    if config["postType"]["offtopic"] and "@doujinmusic" not in post["text"]:
                        payload = {"chat_id": config['telegram']['user_id'],
                                   "text": f"{post['text']} <a href='vk.com/wall{post['from_id']}_{post['id']}'>(link)</a>",
                                   "parse_mode": "HTML"}
                        telegramApi("sendMessage", payload)
                        postCount += 1
            updateScr(postCount)
    time.sleep(config["interval"])
