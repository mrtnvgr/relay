#!/bin/python
import vk_api, telebot, time, json, os

version = "0.0.1"
title = f"Relay v{version}"

def auth_handler(): return input("Authentication code: "), True

def getPosts(count): return vk.wall.get(domain="doujinmusic", offset="1", count=count, sort="desc")

def updateScr(postCount):
	os.system('cls' if os.name == 'nt' else 'clear')
	print(title)
	print(f"Post counter: {postCount}")

config = json.load(open("config.json"))
try:
	history = json.load(open("cache.json"))
except FileNotFoundError:
	history = {"ids": [False]}

vk_session = vk_api.VkApi(config['vk']['login'], config['vk']['password'], auth_handler=auth_handler)
try:
	vk_session.auth()
	print("VK API: Auth success")
except vk_api.exceptions.BadPassword:
	print("VK API: Bad password")
	exit()
vk = vk_session.get_api()

bot = telebot.TeleBot(config["telegram"]["token"], parse_mode="HTML")

postCount = 0
while True:
	updateScr(postCount)
	newPosts = []
	posts = getPosts(str(config["maxHistory"]))["items"]
	for i in posts:
		if i['id'] not in history["ids"] or history["ids"][0]==False:
			whitelist = False
			blacklist = False
			for tag in config["whitelist"]:
				if tag in i["text"]: whitelist = True
			for tag in config["blacklist"]:
				if tag in i["text"]: blacklist = True
			if (whitelist and not blacklist) or ("#статьи@doujinmusic" in i["text"] and config["articles"]) or "@doujinmusic" not in i["text"]: newPosts.append(i)
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
					bot.send_photo(config["telegram"]["user_id"], postPhoto,  caption=f"{post['text']} <a href='vk.com/wall{post['from_id']}_{post['id']}'>(link)</a>\n\n<a href='{file[1]['url']}'>{file[1]['title']}</a>")
					postCount += 1
				else:
					if config["offtopic"] and "@doujinmusic" not in post["text"]:
						bot.send_message(config["telegram"]["user_id"], f"{post['text']} <a href='vk.com/wall{post['from_id']}_{post['id']}'>(link)</a>")
						postCount += 1
			updateScr(postCount)
	time.sleep(config["interval"])
