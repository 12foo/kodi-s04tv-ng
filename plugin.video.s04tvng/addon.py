import sys, os, time, json, re
import xbmcgui, xbmcplugin, xbmcaddon
import requests, requests.utils, json, urlparse
from bs4 import BeautifulSoup

addon_handle = int(sys.argv[1])
addon_base_url = sys.argv[0]
addon_query = urlparse.parse_qs(sys.argv[2][1:])

__addon__ = xbmcaddon.Addon()
__userdata__ = xbmc.translatePath(__addon__.getAddonInfo("profile"))
__loc__ = __addon__.getLocalizedString

if not os.path.exists(__userdata__):
    os.makedirs(__userdata__)

xbmcplugin.setContent(addon_handle, "movies")

login_url = "https://ssl.s04.tv/get_content.php"
feed_url = "http://www.s04.tv"

catfile = os.path.join(__userdata__, "catfile.json")
cookiefile = os.path.join(__userdata__, "cookiefile.json")

session = requests.Session()
username = __addon__.getSetting("username")
password = __addon__.getSetting("password")
if os.path.exists(cookiefile) and os.path.getmtime(catfile) - time.time() < 4 * 60 * 60:
    with open(cookiefile, "r") as cfile:
        session.cookies = requests.utils.cookiejar_from_dict(json.load(cfile))
elif username != "" and password != "":
    params = { "lang": "TV", "form": "login", "username_field": username, "password_field": password }
    r = session.get(login_url, params = params, verify = False)
    if json.loads(r.text[1:-2])["stat"] == "OK":
        with open(cookiefile, "w") as cfile:
            json.dump(requests.utils.dict_from_cookiejar(session.cookies), cfile)
    else:
        xbmcgui.Dialog().ok(__loc__(32001), __loc__(32002), __loc__(32003), __loc__(32004))

def get_subcats(catli):
    uls = catli.find("ul", class_="subnav")
    if uls is None:
        return None
    uls = uls.find("li", recursive=False).find_all("li")
    return [{"name": sc.find("a").text, "link": sc.find("a").get("href")} for sc in uls]

def get_cats():
    # first check if we have a cached categories file younger than 5 minutes
    if os.path.exists(catfile) and os.path.getmtime(catfile) - time.time() < 300:
        with open(catfile, "r") as dumpfile:
            cats = json.load(dumpfile)
        return cats
    # we don't, so get from S04 and overwrite
    homepage = session.get(feed_url + "/de/")
    html = BeautifulSoup(homepage.text, "html.parser")
    catlis = html.find("div", class_="navi-placeholder").find("ul", class_="topnav").find_all("li", recursive=False)
    cats = [{"name": c.find("a").text, "link": c.find("a").get("href"), "subcats": get_subcats(c)} for c in catlis if c.find("a").text not in [u"Home"] and len(c.find("a").text) > 1]
    with open(catfile, "w") as dumpfile:
        json.dump(cats, dumpfile)
    return cats

def get_videos(videopage):
    video_page = session.get(feed_url + videopage)
    html = BeautifulSoup(video_page.text, "html.parser")
    return [{
        "name": " ".join(v.find("span", class_="title").strings),
        "icon": v.find("img").get("src"),
        "link": v.find("a").get("href")
    } for v in html.find("div", id="videoverteil_html").find_all("article")]


if "videopage" in addon_query:
    videos = get_videos(addon_query["videopage"][0])
    for v in videos:
        if v["link"].startswith("https://youtu.be/"):
            url = "plugin://plugin.video.youtube/?path=/root/video&action=play_video&videoid=" + v["link"].replace("https://youtu.be/", "")
        else:
            url = addon_base_url + "?videoplay=" + v["link"]
        li = xbmcgui.ListItem(v["name"], iconImage=v["icon"])
        li.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)
    xbmcplugin.endOfDirectory(addon_handle)

elif "videoplay" in addon_query:
    vid = re.search("/page/(\d+)", addon_query["videoplay"][0])
    if vid is not None:
        vid = vid.group(1)
        vinfo = json.loads(session.get("http://www.s04.tv/webservice/video_xml.php?play=%s&lang=TV&mobile" % (vid,)).text[1:-2])
        if "src" in vinfo:
            token = BeautifulSoup(session.get(vinfo["src"]).text, "html.parser").find("token")
            url = token.get("url") + "?hdnea=" + token.get("auth")
            xbmcplugin.setResolvedUrl(addon_handle, True, xbmcgui.ListItem(path=url))
        else:
            xbmcgui.Dialog().ok(__loc__(32008), __loc__(32009))
            xbmcplugin.setResolvedUrl(addon_handle, False, xbmcgui.ListItem())
else:
    cats = get_cats()
    for i, cat in enumerate(cats):
        if cat["subcats"] is not None:
            for sc in cat["subcats"]:
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=addon_base_url + "?videopage=" + sc["link"], listitem=xbmcgui.ListItem(cat["name"] + " > " + sc["name"]), isFolder=True)
        else:
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=addon_base_url + "?videopage=" + cat["link"], listitem=xbmcgui.ListItem(cat["name"]), isFolder=True)
    xbmcplugin.endOfDirectory(addon_handle)
