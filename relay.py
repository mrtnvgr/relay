#!/bin/python
import requests, time, json, os
from subprocess import Popen

version = "0.0.2"
title = f"Relay v{version}"

def updateScr(postCount):
    os.system('cls' if os.name == 'nt' else 'clear')
    print(title)
    print(f"Post counter: {postCount}")

config = json.load(open("config.json"))
try:
    history = json.load(open("cache.json"))
except FileNotFoundError:
    history = {"ids": [False]}
#https://oauth.vk.com/authorize?client_id=[APP ID]&display=page&scope=wall,groups,offline&response_type=token&v=5.131&state=123456

postCount = 0
while True:
    # update check
    if version!=requests.get("https://api.github.com/repos/mrtnvgr/relay/releases/latest").json()["name"]:
        f = open("updater.py", "w")
        f.write("from subprocess import Popen\nimport requests\nf = open('relay.py', 'w')\nf.write(requests.get('https://raw.githubusercontent.com/mrtnvgr/relay/main/relay.py').text)\nf.close()\nPopen('python relay.py', shell=True)\nexit()")
        f.close()
        Popen("python updater.py", shell=True)
        exit()
    updateScr(postCount)
    newPosts = []
    payload = {"access_token": config["vk"]["token"],
               "domain": "doujinmusic",
               "offset": "1",
               "count": config["maxHistory"],
               "sort": "desc",
               "v": "5.131"}
    posts = requests.get("https://api.vk.com/method/wall.get", params=payload).json()["response"]["items"]
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
            json.dump(history, open("cache.json", "w"))
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
                    requests.get(f"https://api.telegram.org/bot{config['telegram']['token']}/sendPhoto", params=payload)
                    postCount += 1
                else:
                    if config["postType"]["offtopic"] and "@doujinmusic" not in post["text"]:
                        payload = {"chat_id": config['telegram']['user_id'],
                                   "text": f"{post['text']} <a href='vk.com/wall{post['from_id']}_{post['id']}'>(link)</a>",
                                   "parse_mode": "HTML"}
                        requests.get(f"https://api.telegram.org/bot{config['telegram']['token']}/sendMessage", params=payload)
                        postCount += 1
            updateScr(postCount)
    time.sleep(config["interval"])
