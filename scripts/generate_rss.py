import os
import requests
import datetime
import xml.etree.ElementTree as ET

# ================================
# 1. 配置 Notion API 参数
# ================================
NOTION_TOKEN = os.getenv("NOTION_TOKEN")        # 从环境变量获取 Notion 集成令牌 (Notion Integration Token)
DATABASE_ID = os.getenv("DATABASE_ID")          # 从环境变量获取数据库 ID (Database ID)

NOTION_API_URL = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# ================================
# 2. 查询 Notion 数据库（获取所有条目）
# ================================
def query_notion_database():
    """
    查询 Notion 数据库中的所有条目，不进行过滤。
    如果想过滤 Publish Date 等，可自行修改 data。
    """
    data = {
        "page_size": 100
    }
    response = requests.post(NOTION_API_URL, headers=HEADERS, json=data)
    response.raise_for_status()
    data_json = response.json()
    return data_json["results"]

# ================================
# 3. 获取页面块内容 (blocks)
# ================================
def get_page_blocks(page_id):
    """
    根据页面ID，通过 Notion API 获取该页面的所有块内容。
    """
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    return data.get("results", [])

# ================================
# 4. 将 Notion 块转换为 HTML
# ================================
def convert_blocks_to_html(blocks):
    """
    遍历 Notion 页面块，将不同类型的块转换为 HTML。
    支持:
      - paragraph: 段落
      - heading_1: 标题1
      - file: 文件(如PDF)
      - image: 图片
    其他类型可根据需要继续扩展
    """
    html_fragments = []
    for block in blocks:
        block_type = block.get("type")

        if block_type == "paragraph":
            paragraph_text = ""
            for text_item in block["paragraph"]["rich_text"]:
                text_content = text_item.get("plain_text", "")
                annotations = text_item.get("annotations", {})
                # 简单加粗、斜体
                if annotations.get("bold"):
                    text_content = f"<strong>{text_content}</strong>"
                if annotations.get("italic"):
                    text_content = f"<em>{text_content}</em>"
                # 链接
                if text_item.get("text", {}).get("link"):
                    link_url = text_item["text"]["link"].get("url", "#")
                    text_content = f'<a href="{link_url}">{text_content}</a>'
                paragraph_text += text_content
            html_fragments.append(f"<p>{paragraph_text}</p>")

        elif block_type == "heading_1":
            heading_text = "".join([t.get("plain_text", "") for t in block["heading_1"]["rich_text"]])
            html_fragments.append(f"<h1>{heading_text}</h1>")

        elif block_type == "file":
            file_info = block["file"]
            file_url = ""
            # 判断外部链接还是 Notion 上传
            if "external" in file_info:
                file_url = file_info["external"].get("url", "")
            elif "file" in file_info:
                file_url = file_info["file"].get("url", "")
            file_name = block.get("name", "Download File")
            html_fragments.append(f'<p><a href="{file_url}" download>{file_name}</a></p>')

        elif block_type == "image":
            image_data = block["image"]
            if image_data["type"] == "file":
                image_url = image_data["file"]["url"]
            else:  # external
                image_url = image_data["external"]["url"]
            caption_text = ""
            if image_data.get("caption"):
                caption_text = " ".join([c["plain_text"] for c in image_data["caption"]])
            img_html = f'<img src="{image_url}" alt="{caption_text}" />'
            if caption_text:
                img_html += f'<p><em>{caption_text}</em></p>'
            html_fragments.append(img_html)

        # 你可以继续扩展其他块类型: heading_2, bulleted_list_item, to_do, embed, video, 等等

    return "\n".join(html_fragments)

# ================================
# 5. 生成 RSS XML
# ================================
def generate_rss(items):
    """
    遍历 Notion 数据库条目，为每个条目获取页面块内容 (HTML)，
    然后生成 RSS 的 <item> 标签。

    - <description>：仅放简短文本(不使用 CDATA)，避免Inoreader显示 "CDATA["
    - <content:encoded>：使用<![CDATA[...]]> 包裹完整富文本，让阅读器渲染HTML
    """
    # 在根节点上添加 content 命名空间
    rss = ET.Element("rss", version="2.0", attrib={"xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Daily Reading"
    ET.SubElement(channel, "link").text = "https://yourusername.github.io/notion-to-rss"
    ET.SubElement(channel, "description").text = "Generated from Notion."

    for item in items:
        properties = item.get("properties", {})
        page_id = item.get("id", "")
        
        # 获取标题
        title_text = "No Title"
        if "Title" in properties:
            title_data = properties["Title"]["title"]
            if title_data:
                title_text = title_data[0].get("plain_text", "No Title")

        # 获取页面块并转换为富文本HTML
        blocks = get_page_blocks(page_id)
        page_html = convert_blocks_to_html(blocks)

        # 创建 <item>
        item_elem = ET.SubElement(channel, "item")
        ET.SubElement(item_elem, "title").text = title_text

        # 构造链接(示例)，可改为你想要的链接
        notion_link = "https://www.notion.so/" + page_id.replace("-", "")
        ET.SubElement(item_elem, "link").text = notion_link

        # (1) <description>：只放简短文本，避免显示 "CDATA["
        description_elem = ET.SubElement(item_elem, "description")
        description_elem.text = f"这是简要描述：{title_text}"

        # (2) <content:encoded>：用 CDATA 包裹完整HTML
        content_elem = ET.SubElement(item_elem, "{http://purl.org/rss/1.0/modules/content/}encoded")
        content_elem.text = f"<![CDATA[{page_html}]]>"

        # pubDate
        pub_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item_elem, "pubDate").text = pub_date

    # 转换为XML字符串
    rss_xml = ET.tostring(rss, encoding="utf-8", method="xml").decode("utf-8")
    # 修复 ElementTree 将 CDATA 标记转义的问题
    rss_xml = rss_xml.replace("&lt;![CDATA[", "<![CDATA[").replace("]]&gt;", "]]>")
    return rss_xml

# ================================
# 6. 主函数
# ================================
def main():
    # 1) 获取数据库条目
    items = query_notion_database()
    # 2) 生成RSS
    rss_content = generate_rss(items)
    # 3) 写入 docs/rss.xml
    with open("docs/rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)
    print("RSS generated and written to docs/rss.xml")

if __name__ == "__main__":
    main()
