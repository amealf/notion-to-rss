import os
import requests
import datetime
import xml.etree.ElementTree as ET

# 从环境变量获取 Notion Integration（Notion 集成）的令牌和数据库ID
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# Notion API 的查询URL
NOTION_API_URL = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

# 请求头，需包含授权信息和 Notion API 版本
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def query_notion_database():
    """
    从 Notion 数据库中获取当日需要发布的记录（通过 Publish Date 字段过滤）。
    """
    # 获取当前日期（形如 2023-03-17），并用来匹配 Publish Date（发布日期）
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # 构建过滤条件：只获取发布日期 == 今天 的条目
    data = {
        "filter": {
            "property": "Publish Date",
            "date": {
                "equals": today_str
            }
        }
    }
    response = requests.post(NOTION_API_URL, headers=HEADERS, json=data)
    response.raise_for_status()

    # 返回数据库查询结果列表
    return response.json()["results"]

def generate_rss(items):
    """
    根据从 Notion 获取的记录生成 RSS（RSS，原文）内容。
    """
    # 创建 <rss> 根节点（version="2.0"）
    rss = ET.Element("rss", version="2.0")
    # 创建 <channel> 子节点
    channel = ET.SubElement(rss, "channel")

    # 为频道添加基础信息
    ET.SubElement(channel, "title").text = "Daily Reading"  # RSS标题
    ET.SubElement(channel, "link").text = "https://yourusername.github.io/notion-to-rss"  # 你GitHub Pages的URL
    ET.SubElement(channel, "description").text = "Generated from Notion."

    # 遍历 Notion 返回的记录，构建 <item> 节点
    for item in items:
        properties = item["properties"]

        # 获取标题
        # 注意：这里假设你的 Notion 数据库标题字段名是 "Title"
        title_data = properties["Title"]["title"]
        title = title_data[0]["plain_text"] if title_data else "No Title"

        # 获取链接
        # 注意：这里假设你的 Notion 数据库里有一个URL字段名是 "URL"
        url_data = properties["URL"]["url"]
        url = url_data if url_data else "https://example.com"

        # 设置 RSS 项目的发布时间（此处直接用脚本生成的当前时间）
        pub_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")

        # 构建 <item>
        item_elem = ET.SubElement(channel, "item")
        ET.SubElement(item_elem, "title").text = title
        ET.SubElement(item_elem, "link").text = url
        ET.SubElement(item_elem, "pubDate").text = pub_date

    # 将整个 <rss> 树转换为字符串
    rss_xml = ET.tostring(rss, encoding="utf-8", method="xml").decode("utf-8")
    return rss_xml

def main():
    # 从 Notion 查询数据
    items = query_notion_database()
    # 生成 RSS 内容
    rss_content = generate_rss(items)

    # 将生成的内容写入 docs/rss.xml 文件
    # 注意：这里将原先的 "public/rss.xml" 改为了 "docs/rss.xml"
    with open("docs/rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)

if __name__ == "__main__":
    main()

