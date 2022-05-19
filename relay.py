#!/bin/python
import requests, argparse, threading, time, json, os, sys
from subprocess import Popen
from random import randint

version = "0.1.2"
title = f"Relay v{version}"

def updateScr():
    global postCount
    global inlineRequestsCount
    os.system('cls' if os.name == 'nt' else 'clear')
    print(title)
    print(f"Post counter: {postCount}")
    print(f"Inline requests: {inlineRequestsCount}")

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", default="config.json")
parser.add_argument("-nc", "--no-cache", action="store_true")
args = parser.parse_args()

REPLYMARKUP = '{"inline_keyboard": [[{"text": "!LIKESIGN!", "callback_data": "\/like"}]]}'
startTime = time.monotonic()

if args.config[:4]=="url:":
    config = json.loads(requests.get(args.config[4:]).text)
else:
    config = json.load(open(args.config))
    if "url" in config:
        config = json.loads(requests.get(config["url"]).text)

history = {"ids": [False]}
if not args.no_cache:
    try:
        history = json.load(open("cache.json"))
    except FileNotFoundError:
        pass    
#https://oauth.vk.com/authorize?client_id=[APP ID]&display=page&scope=wall,groups,offline&response_type=token&v=5.131&state=123456

def updater_maker(filename, fileurl, executable):
    apiRequest("telegram", "sendMessage", {"chat_id": config['telegram']['user_id'], "text": "info: update"})
    if executable:
        string = f'from subprocess import Popen\nimport requests\nf = open("{filename}", "w", encoding="utf-8")\nf.write(requests.get(f"{fileurl}").text)\nf.close()i\nPopen("python {filename}", shell=True)\nexit()'
        f = open("updater.py", "w")
        f.write(string)
        f.close()
        Popen("python updater.py", shell=True)
        exit(0)
    else:
        f = open(filename, "w", encoding="utf-8")
        f.write(requests.get(fileurl).text)
        f.close()
        os.execl(sys.executable, sys.executable, *sys.argv)


def apiRequest(service, method, payload):
    if service=="telegram":
        return requests.Session().get(f"https://api.telegram.org/bot{config['telegram']['token']}/{method}", params=payload).json()
    elif service=="vk":
        return requests.Session().get(f"https://api.vk.com/method/{method}", params=payload | {"access_token": config['vk']['token'], "v": "5.131"}).json()

def get_updates(config):
    result = apiRequest("telegram", "getUpdates", {})
    if result['ok']==True and result["result"]!=[]:
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
                if "message" in message.keys():
                    if message['message']['from']['id']!=config['telegram']['user_id']: continue
                    if "text" in message["message"].keys():
                        text = message["message"]["text"]
                    else:
                        text = "/update"
                    payload = {"chat_id": config['telegram']['user_id'], "text": "warning: invalid command"}
                    if text=="/help":
                        payload["text"] = f"{title}\ngithub.com/mrtnvgr/relay\n\n/online - check if bot is online\n/update - config files update\n/uptime - get script uptime"
                    elif text=="/online":
                        payload["text"] = f"online:\n    Main thread: {mainThread.is_alive()}\n    Reply thread: {replierThread.is_alive()}"
                    elif text=="/uptime":
                        payload["text"] = time.strftime("uptime: %M minutes %S seconds", time.localtime(time.monotonic()-startTime))
                    elif text=="/update":
                        if "document" in message["message"]:
                            filepath = apiRequest("telegram", "getFile", {"file_id": message["message"]["document"]["file_id"]})["result"]["file_path"]
                            filename = message["message"]["document"]["file_name"]
                            updater_maker(filename, f"https://api.telegram.org/file/bot{config['telegram']['token']}/{filepath}", False)
                    if text!="/update": apiRequest("telegram", "sendMessage", payload)
                elif "callback_query" in message.keys():
                    if message['callback_query']['from']['id']!=config['telegram']['user_id']: continue
                    for entity in message["callback_query"]["message"]["caption_entities"]:
                        if entity["type"]=="text_link" and "wall" in entity["url"]:
                            postUrl = entity["url"].split("_")
                            message_id = message["callback_query"]["message"]["message_id"]
                            for button in message["callback_query"]["message"]["reply_markup"]["inline_keyboard"][0]:
                                if button["callback_data"]=="/like":
                                    if button["text"]=="🖤":
                                        likeButtonText = "❤️"
                                        likeButtonMethod = "likes.delete"
                                    else:
                                        likeButtonText = "🖤"
                                        likeButtonMethod = "likes.add"
                                    likes = apiRequest("vk", likeButtonMethod, {"type": "post", "owner_id": "-"+postUrl[0].split("-")[1], "item_id": postUrl[1]})
                                    apiRequest("telegram", "editMessageReplyMarkup", {"chat_id": config["telegram"]["user_id"], "message_id": message_id, "reply_markup": REPLYMARKUP.replace("!LIKESIGN!", likeButtonText)})
                                    apiRequest("telegram", "answerCallbackQuery", {"callback_query_id": message["callback_query"]["id"], "text": f"Total Likes: {likes['response']['likes']}", "show_alert": True})
                                    break
                elif "inline_query" in message.keys():
                    if message["inline_query"]["query"]!="":
                        payload = {"domain": "doujinmusic",
                                   "count": "100",
                                   "offset": "1",
                                   "query": message["inline_query"]["query"]}
                        user_id = message["inline_query"]["from"]["id"]
                        if (config["inlineOwnerOnly"] and user_id==config["telegram"]["user_id"]) or (config["inlineOwnerOnly"]!=True):
                            search_posts = apiRequest("vk", "wall.search", payload)
                            postCheck(search_posts["response"]["items"], inline=True, inline_id=message["inline_query"]["id"])

def postCheck(newPosts, inline=False, inline_id=0):
    global postCount
    global inlineRequestsCount
    results = []
    if len(newPosts)>0:
        for post in newPosts:
            if inline==False:
                history["ids"].append(post['id'])
                if history["ids"][0]==False: history["ids"].pop(0)
                if len(history["ids"])>config["maxHistory"]: history["ids"] = history["ids"][-config["maxHistory"]:]
                if not args.no_cache: json.dump(history, open("cache.json", "w"))
            file = [False, False]
            postPlaylist = ""
            if post["likes"]["user_likes"]==0:
                likeButtonText = "❤️"
            else:
                likeButtonText = "🖤"
            if "attachments" in post:
                for attachment in post["attachments"]:
                    if attachment["type"]=="doc":
                        filetype = attachment["doc"]["title"]
                        if "[FLAC]" in filetype or "[WAV]" in filetype:
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
                    elif attachment["type"]=="link":
                        if attachment["link"]["description"]=="Плейлист":
                            postPlaylist = attachment["link"]["url"]
                if file[1]!=False:
                    payload = {"chat_id": config['telegram']['user_id'],
                                "photo": postPhoto,
                                "caption": f"{post['text']} <a href='vk.com/wall{post['from_id']}_{post['id']}'>(link)</a>\n<a href='{postPlaylist}'>Playlist</a>\n\n<a href='{file[1]['url']}'>{file[1]['title']}</a>",
                                "reply_markup": REPLYMARKUP.replace("!LIKESIGN!", likeButtonText),
                                "parse_mode": "HTML"}
                    if not inline:
                        apiRequest("telegram", "sendPhoto", payload)
                        postCount += 1
                    else:
                        payload.pop("chat_id")
                        payload.pop("reply_markup")
                        payload["id"] = str(post["id"])
                        payload["type"] = "photo"
                        payload["title"] = post["text"]
                        payload["photo_url"] = payload.pop("photo")
                        payload["thumb_url"] = payload["photo_url"]
                        results.append(json.dumps(payload))
            else:
                if (config["postType"]["offtopic"] and "@doujinmusic" not in post["text"]) and not inline:
                    payload = {"chat_id": config['telegram']['user_id'],
                                "text": f"{post['text']} <a href='vk.com/wall{post['from_id']}_{post['id']}'>(link)</a>",
                                "reply_markup": REPLYMARKUP.replace("!LIKESIGN!", likeButtonText),
                                "parse_mode": "HTML"}
                    apiRequest("telegram", "sendMessage", payload)
                    postCount += 1
        if inline:
            inlineRequestsCount += 1
            apiRequest("telegram", "answerInlineQuery", {"inline_query_id": inline_id, "results": f'[{",".join(results)}]'})
            updateScr()
    else:
        if inline:
            apiRequest("telegram", "answerInlineQuery", {"inline_query_id": inline_id, "results": '[{"type": "article", "id": "0", "title": "404 Not found", "message_text": "(－‸ლ)"}]'})

def main():
    global postCount
    global inlineRequestsCount
    postCount = 0
    inlineRequestsCount = 0
    remote_version = requests.get("https://api.github.com/repos/mrtnvgr/relay/releases/latest").json()
    if "name" in remote_version.keys():
        if version!=remote_version["name"]:
            updater_maker("relay.py", "https://raw.githubusercontent.com/mrtnvgr/relay/main/relay.py", True)
            exit(0)
    updateScr()
    newPosts = []
    payload = {"domain": "doujinmusic",
               "offset": "1",
               "count": config["maxHistory"],
               "sort": "desc"}
    posts = apiRequest("vk", "wall.get", payload)
    if 'error' in posts.keys():
        print("error: vk api failure")
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
    postCheck(newPosts)
    updateScr()
    time.sleep(config["interval"])


replierThread = threading.Thread(target=replier, args=(config,))
replierThread.daemon = True

mainThread = threading.Thread(target=main)
mainThread.daemon = True

if __name__=="__main__":
    apiRequest("telegram", "sendMessage", {"chat_id": config['telegram']['user_id'], "text": "info: restart"})
    while True:
        try:
            if not replierThread.is_alive(): replierThread.start()
            if not mainThread.is_alive(): mainThread.start()
            time.sleep(10)
        except Exception as e:
            apiRequest("telegram", "sendMessage", {"chat_id": config['telegram']['user_id'], "text": f"error: {e}"})
