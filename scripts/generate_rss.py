import os
import requests
import datetime
import xml.etree.ElementTree as ET

# ================================
# 1. 配置 Notion API 参数 (API parameters)
# ================================
NOTION_TOKEN = os.getenv("NOTION_TOKEN")        # 从环境变量获取 Notion 集成令牌
DATABASE_ID = os.getenv("DATABASE_ID")          # 从环境变量获取数据库 ID

# Notion 数据库查询 URL (URL for querying the Notion database)
NOTION_API_URL = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
# HTTP 请求头 (HTTP headers)，必须包含 Authorization、Notion-Version、Content-Type
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# ================================
# 2. 查询 Notion 数据库中的所有记录 (Query all records in the Notion database)
# ================================
def query_notion_database():
    """
    查询 Notion 数据库中的所有条目，不进行额外的过滤。
    这样即使某些字段为空也会被返回。
    """
    data = {
        "page_size": 100
    }
    response = requests.post(NOTION_API_URL, headers=HEADERS, json=data)
    response.raise_for_status()
    data_json = response.json()
    # 调试：可以打印返回条目的数量
    # print("Number of items returned:", len(data_json["results"]))
    return data_json["results"]

# ================================
# 3. 获取 Notion 页面块内容 (Get page blocks)
# ================================
def get_page_blocks(page_id):
    """
    根据页面 ID，通过 Notion API 获取该页面的所有块内容。
    使用接口 /v1/blocks/{block_id}/children 获取页面下的块。
    """
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    return data.get("results", [])

# ================================
# 4. 将 Notion 块转换为 HTML (Convert blocks to HTML)
# ================================
def convert_blocks_to_html(blocks):
    """
    遍历 Notion 页面块，将不同类型的块转换为 HTML 格式。
    支持：
      - paragraph：段落文本（支持加粗、斜体、链接）
      - heading_1：标题 1
      - heading_2：标题 2
      - file：文件块（例如 PDF），生成下载链接
      - image：图片块，生成 <img> 标签显示图片
    其他类型可根据需求继续扩展。
    """
    html_fragments = []
    for block in blocks:
        block_type = block.get("type")
        
        # 处理段落文本 (paragraph)
        if block_type == "paragraph":
            paragraph_text = ""
            for text_item in block["paragraph"]["rich_text"]:
                text_content = text_item.get("plain_text", "")
                annotations = text_item.get("annotations", {})
                # 处理加粗和斜体 (bold and italic)
                if annotations.get("bold"):
                    text_content = f"<strong>{text_content}</strong>"
                if annotations.get("italic"):
                    text_content = f"<em>{text_content}</em>"
                # 如果有链接则转换为 <a> 标签 (link)
                link_info = text_item.get("text", {}).get("link")
                if link_info:
                    link_url = link_info.get("url", "#")
                    text_content = f'<a href="{link_url}">{text_content}</a>'
                paragraph_text += text_content
            html_fragments.append(f"<p>{paragraph_text}</p>")
        
        # 处理标题 1 (heading_1)
        elif block_type == "heading_1":
            heading_text = "".join([t.get("plain_text", "") for t in block["heading_1"]["rich_text"]])
            html_fragments.append(f"<h1>{heading_text}</h1>")
        
        # 处理标题 2 (heading_2)
        elif block_type == "heading_2":
            heading_text = "".join([t.get("plain_text", "") for t in block["heading_2"]["rich_text"]])
            html_fragments.append(f"<h2>{heading_text}</h2>")
        
        # 处理文件块 (file block，例如 PDF)
        elif block_type == "file":
            file_info = block["file"]
            file_url = ""
            # 判断文件类型：外部链接或 Notion 内部上传
            if "external" in file_info:
                file_url = file_info["external"].get("url", "")
            elif "file" in file_info:
                file_url = file_info["file"].get("url", "")
            file_name = block.get("name", "Download File")
            html_fragments.append(f'<p><a href="{file_url}" download>{file_name}</a></p>')
        
        # 处理图片块 (image block)
        elif block_type == "image":
            image_data = block["image"]
            image_url = ""
            if image_data["type"] == "external":
                image_url = image_data["external"].get("url", "")
            elif image_data["type"] == "file":
                image_url = image_data["file"].get("url", "")
            if image_url:
                html_fragments.append(f'<p><img src="{image_url}" alt="Image"/></p>')
        
        # 可扩展其他块类型，如列表、待办事项等
        
    return "\n".join(html_fragments)

# ================================
# 5. 更新 Notion 页面属性 (Update Notion page properties)
# ================================
def update_notion_page(page_id):
    """
    使用 Notion API 更新页面属性，将 Status 修改为 Published，
    同时将 Publish Date 更新为当前日期（ISO 格式）。
    """
    update_url = f"https://api.notion.com/v1/pages/{page_id}"
    today_date = datetime.date.today().isoformat()  # 当前日期，如 "2025-03-18"
    update_data = {
        "properties": {
            "Status": {"select": {"name": "Published"}},
            "Publish Date": {"date": {"start": today_date}}
        }
    }
    response = requests.patch(update_url, headers=HEADERS, json=update_data)
    response.raise_for_status()
    return response.json()

# ================================
# 6. 生成 RSS XML (Generate RSS XML)
# ================================
def generate_rss(items):
    """
    遍历 Notion 数据库条目，为每个条目调用 get_page_blocks 和 convert_blocks_to_html
    获取富文本内容，并生成 RSS 的 <item> 标签。

    每个 <item> 包括：
      - <title>：使用 Notion 的标题属性（此处默认列名为 "Title"）
      - <link>：构造一个示例链接，可修改为实际 Notion 页面链接
      - <description> 和 <content:encoded>：输出 HTML 格式的页面内容，使用 <![CDATA[...]]> 包裹，确保 HTML 不被转义
      - <pubDate>：发布时间，使用当前系统时间（也可以改为 Notion 中的日期）
    """
    # 创建 RSS 根节点，并添加 content 命名空间，用于 <content:encoded>
    rss = ET.Element("rss", version="2.0", attrib={"xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Daily Reading"
    ET.SubElement(channel, "link").text = "https://yourusername.github.io/notion-to-rss"
    ET.SubElement(channel, "description").text = "Generated from Notion."

    for item in items:
        properties = item.get("properties", {})
        # 获取标题（假定标题属性名称为 "Title"）
        title_text = "No Title"
        if "Title" in properties:
            title_data = properties["Title"]["title"]
            if title_data:
                title_text = title_data[0].get("plain_text", "No Title")
        
        # 使用数据库条目的 id 作为页面 id
        page_id = item.get("id")
        
        # -------------------------------
        # 更新已发布的笔记 (Update published note)
        # -------------------------------
        update_notion_page(page_id)
        
        # 获取页面块内容，并转换为 HTML
        blocks = get_page_blocks(page_id)
        page_html = convert_blocks_to_html(blocks)

        # 创建 RSS <item>
        item_elem = ET.SubElement(channel, "item")
        ET.SubElement(item_elem, "title").text = title_text
        # 示例链接：构造一个指向 Notion 页面链接的 URL（实际情况请修改）
        ET.SubElement(item_elem, "link").text = "https://www.notion.so/" + page_id.replace("-", "")
        
        # 同时输出 <content:encoded> 标签
        content_elem = ET.SubElement(item_elem, "{http://purl.org/rss/1.0/modules/content/}encoded")
        content_elem.text = page_html
        
        # 设置发布日期（此处用当前系统时间，格式符合 RFC-822）
        pub_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item_elem, "pubDate").text = pub_date

    # 将整个 XML 树转换为字符串
    rss_xml = ET.tostring(rss, encoding="utf-8", method="xml").decode("utf-8")
    return rss_xml

# ================================
# 7. 主函数：查询、生成并写入 RSS (Main function)
# ================================
def main():
    # 查询 Notion 数据库中的所有条目
    items = query_notion_database()
    # 生成 RSS XML 内容
    rss_content = generate_rss(items)
    # 将 RSS 写入到 docs/rss.xml（确保 docs 文件夹存在）
    with open("docs/rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)
    print("RSS generated and written to docs/rss.xml")

if __name__ == "__main__":
    main()
