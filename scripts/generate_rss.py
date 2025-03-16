import os
import requests
import datetime
import xml.etree.ElementTree as ET

# 1. 从环境变量中获取 Notion Integration 的令牌和数据库ID
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

# 2. 配置 Notion API 相关参数
NOTION_API_URL = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def query_notion_database():
    """
    查询 Notion 数据库：
    让 'Publish Date' 等于今天 或者 为空 的条目都被获取到。
    如果你想获取所有条目，不考虑日期，可将 data 改为 {}。
    """

    # 获取当前日期（形如 "2025-03-16"）
    today_str = datetime.date.today().isoformat()

    # 使用 OR 逻辑：
    # 1) Publish Date = 今天
    # 2) Publish Date 为空
    data = {
        "filter": {
            "or": [
                {
                    "property": "Publish Date",
                    "date": {
                        "equals": today_str
                    }
                },
                {
                    "property": "Publish Date",
                    "date": {
                        "is_empty": True
                    }
                }
            ]
        },
        # 如果你想一次获取更多条目，可设置 page_size
        "page_size": 100
    }

    response = requests.post(NOTION_API_URL, headers=HEADERS, json=data)
    response.raise_for_status()
    data_json = response.json()
    
    # 调试用：可以打印看看返回了多少条
    # print("Raw response from Notion:", data_json)
    # print("Number of items returned:", len(data_json["results"]))

    return data_json["results"]

def generate_rss(items):
    """
    将 Notion 数据库返回的记录转换为 RSS 格式。
    对于空字段（URL、Type、Publish Date、Status），使用默认值。
    """

    # 创建 <rss version="2.0"> 根节点
    rss = ET.Element("rss", version="2.0")
    # 创建 <channel> 子节点
    channel = ET.SubElement(rss, "channel")

    # 设置频道的基本信息
    ET.SubElement(channel, "title").text = "Daily Reading"
    ET.SubElement(channel, "link").text = "https://yourusername.github.io/notion-to-rss"
    ET.SubElement(channel, "description").text = "Generated from Notion."

    # 遍历每条记录
    for item in items:
        properties = item["properties"]

        # 1) Title
        #   - Notion 中的标题属性通常是 properties["Title"]["title"]
        #   - 如果字段名不是 "Title"，请改为实际名称
        title_data = properties["Title"]["title"]
        title = title_data[0]["plain_text"] if title_data else "No Title"

        # 2) URL
        #   - 如果为空，就用一个占位符，如 "No URL"
        #   - 如果字段名不是 "URL"，请改为实际名称
        url_value = None
        if "URL" in properties and properties["URL"]["url"] is not None:
            url_value = properties["URL"]["url"]
        url = url_value if url_value else "No URL"

        # 3) Type
        #   - 如果为空，就用 "No Type"
        #   - 如果字段名不是 "Type"，请改为实际名称
        type_value = None
        if "Type" in properties and properties["Type"]["select"] is not None:
            type_value = properties["Type"]["select"]["name"]
        item_type = type_value if type_value else "No Type"

        # 4) Publish Date
        #   - 如果为空，就用 "No Publish Date"
        #   - 如果字段名不是 "Publish Date"，请改为实际名称
        pub_date_str = "No Publish Date"
        if "Publish Date" in properties and properties["Publish Date"]["date"]:
            # 可能是 properties["Publish Date"]["date"]["start"]
            pub_date_str = properties["Publish Date"]["date"]["start"]

        # 5) Status
        #   - 如果为空，就用 "No Status"
        #   - 如果字段名不是 "Status"，请改为实际名称
        status_value = None
        if "Status" in properties and properties["Status"]["select"] is not None:
            status_value = properties["Status"]["select"]["name"]
        item_status = status_value if status_value else "No Status"

        # 创建 <item> 节点
        item_elem = ET.SubElement(channel, "item")

        # <title>：显示标题
        ET.SubElement(item_elem, "title").text = title

        # <link>：在 RSS 中点击可跳转到链接，如果没有URL就放置 "No URL"
        ET.SubElement(item_elem, "link").text = url

        # <description>：可用于展示更多信息，如 Type、Status、Publish Date
        # 你也可以把更多字段组合起来放这里
        desc_text = f"Type: {item_type}\nStatus: {item_status}\nPublish Date: {pub_date_str}"
        ET.SubElement(item_elem, "description").text = desc_text

        # <pubDate>：RSS 专用发布日期，这里可以用系统当前时间或 Notion 里的日期
        # 为了保证 RSS 阅读器识别，建议用 RFC-822 格式
        pub_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item_elem, "pubDate").text = pub_date

    # 将整棵树转换为字符串
    rss_xml = ET.tostring(rss, encoding="utf-8", method="xml").decode("utf-8")
    return rss_xml

def main():
    # 1) 从 Notion 查询数据
    items = query_notion_database()
    # 2) 生成 RSS 内容
    rss_content = generate_rss(items)
    # 3) 写入 docs/rss.xml
    #    确保你的仓库中有 docs 文件夹，并在 GitHub Pages 设置里选了 docs
    with open("docs/rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)

if __name__ == "__main__":
    main()
