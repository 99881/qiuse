#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每天 20:30（北京时间）把「今晚准备 + 明天行程」推到飞书/企业微信/钉钉群机器人。

需要的环境变量（配一个就行）：
  FEISHU_WEBHOOK   飞书群机器人地址
  WECOM_WEBHOOK    企业微信群机器人地址
  DINGTALK_WEBHOOK 钉钉群机器人地址
可选：
  RUN_DATE         手动指定“今天”，格式 2026-11-14（默认用北京时间今天）
  DRY_RUN=1        只打印，不发送
"""
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
TZ = dt.timezone(dt.timedelta(hours=8))


def load_trip():
    with open(os.path.join(ROOT, "trip.json"), encoding="utf-8") as f:
        return json.load(f)["days"]


def today_shanghai():
    env = os.environ.get("RUN_DATE")
    if env:
        return dt.datetime.strptime(env, "%Y-%m-%d").date()
    return dt.datetime.now(TZ).date()


def find_day(days, d):
    for x in days:
        if x["date"] == d.isoformat():
            return x
    return None


def fetch_weather(day):
    url = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
           "precipitation_sum&start_date={d}&end_date={d}&timezone=Asia%2FShanghai"
           ).format(lat=day["lat"], lon=day["lon"], d=day["date"])
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            j = json.load(r)
        d = j["daily"]
        return (d["temperature_2m_max"][0], d["temperature_2m_min"][0],
                d["precipitation_probability_max"][0], d["precipitation_sum"][0])
    except Exception as e:  # 天气挂了也要能推
        print("weather failed:", e, file=sys.stderr)
        return None


def build(days, today):
    tomorrow = today + dt.timedelta(days=1)
    day = find_day(days, tomorrow)
    if not day:
        return None
    wx = fetch_weather(day)
    lines = []
    lines.append("【明天 {} {}】".format(day["label"], tomorrow.strftime("%m/%d")))
    lines.append(day["plan"])
    lines.append("住：" + day["stay"])
    if wx:
        hi, lo, pp, mm = wx
        lines.append("天气：{:.0f}—{:.0f}℃，降雨 {}%，{} mm".format(lo, hi, pp, mm))
    lines.append("")
    lines.append("今晚要做：")
    for i, p in enumerate(day["prep"], 1):
        lines.append("{}. {}".format(i, p))
    lines.append("")
    lines.append("注意：" + day["risk"])
    lines.append("详细版 https://99881.github.io/qiuse/")
    return "\n".join(lines)


def send(text):
    if os.environ.get("DRY_RUN") == "1":
        print(text)
        return
    payloads = []
    if os.environ.get("FEISHU_WEBHOOK"):
        payloads.append((os.environ["FEISHU_WEBHOOK"],
                         {"msg_type": "text", "content": {"text": text}}))
    if os.environ.get("WECOM_WEBHOOK"):
        payloads.append((os.environ["WECOM_WEBHOOK"],
                         {"msgtype": "text", "text": {"content": text}}))
    if os.environ.get("DINGTALK_WEBHOOK"):
        payloads.append((os.environ["DINGTALK_WEBHOOK"],
                         {"msgtype": "text", "text": {"content": text}}))
    if not payloads:
        print(text)
        print("\n[未配置 WEBHOOK，只打印]", file=sys.stderr)
        return
    for url, body in payloads:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                print("sent:", r.status, r.read()[:200])
        except Exception as e:
            print("send failed:", e, file=sys.stderr)
            raise


def main():
    days = load_trip()
    text = build(days, today_shanghai())
    if not text:
        print("今天之后没有行程了")
        return
    send(text)


if __name__ == "__main__":
    main()
