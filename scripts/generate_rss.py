import os
import requests
import datetime
import xml.etree.ElementTree as ET

# ================================
# 1. 配置 Notion API 参数 (API parameters)
# ================================
NOTION_TOKEN = os.getenv("NOTION_TOKEN")        # 从环境变量获取 Notion 集成令牌 (Notion Integration Token)
DATABASE_ID = os.getenv("DATABASE_ID")          # 从环境变量获取数据库 ID (Database ID)

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
    查询 Notion 数据库中的所有条目。
    """
    data = {
        "page_size": 100
    }
    response = requests.post(NOTION_API_URL, headers=HEADERS, json=data)
    response.raise_for_status()
    data_json = response.json()
    return data_json["results"]

# ================================
# 3. 获取 Notion 页面块内容 (Get page blocks from a Notion page)
# ================================
def get_page_blocks(page_id):
    """
    根据页面 ID，通过 Notion API 获取该页面下所有块内容。
    """
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    return data.get("results", [])

# ================================
# 4. 将 Notion 块转换为 HTML (Convert Notion blocks to HTML)
# ================================
def convert_blocks_to_html(blocks):
    """
    遍历 Notion 页面块，将支持的块类型转换为 HTML。
    支持：paragraph, heading_1, heading_2, file, image。
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
                if annotations.get("bold"):
                    text_content = f"<strong>{text_content}</strong>"
                if annotations.get("italic"):
                    text_content = f"<em>{text_content}</em>"
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
        
        # 其他块类型可根据需求扩展
        
    return "\n".join(html_fragments)

# ================================
# 5. 更新 Notion 页面属性 (Update Notion page properties)
# ================================
def update_notion_page(page_id):
    """
    使用 Notion API 更新页面属性，将 Status 修改为 Published，
    同时将 Publish Date 更新为当前日期 (ISO 格式)。
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
    遍历 Notion 数据库条目，为每个未推送（Status 不为 Published）的条目：
      - 更新页面属性（将 Status 更新为 Published，设置 Publish Date）
      - 获取页面块内容，并转换为 HTML
      - 在文章开头插入 source 链接（使用 Notion 数据库中 "url" 列的值），空一行后再接正文内容
      - 生成 RSS 的 <item> 标签
    """
    rss = ET.Element("rss", version="2.0", attrib={"xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Daily Reading"
    ET.SubElement(channel, "link").text = "https://yourusername.github.io/notion-to-rss"
    ET.SubElement(channel, "description").text = "Generated from Notion."

    for item in items:
        properties = item.get("properties", {})

        # 仅推送 Status 不为 'Published' 的笔记 (Only process notes with Status != 'Published')
        status_select = properties.get("Status", {}).get("select")
        if status_select and status_select.get("name") == "Published":
            continue

        # 获取标题，假定标题属性名称为 "Title"
        title_text = "No Title"
        if "Title" in properties:
            title_data = properties["Title"]["title"]
            if title_data:
                title_text = title_data[0].get("plain_text", "No Title")
        
        # 使用数据库条目的 id 作为页面 id
        page_id = item.get("id")
        
        # 从 Notion 数据库中的 "url" 列获取链接值 (Get the URL from the "url" column)
        source_url = None
        if "url" in properties:
            source_url = properties["url"].get("url")
        # 如果 "url" 列为空，则回退使用 Notion 页面链接 (Fallback to Notion page URL)
        if not source_url:
            source_url = "https://www.notion.so/" + page_id.replace("-", "")
        
        # 更新页面属性：将 Status 更新为 Published，并设置 Publish Date
        update_notion_page(page_id)
        
        # 获取页面块内容，并转换为 HTML
        blocks = get_page_blocks(page_id)
        page_html = convert_blocks_to_html(blocks)
        
        # 在文章开头插入 source 链接和空行
        source_html = f'<p>source: <a href="{source_url}">{source_url}</a></p><p></p>'
        page_html = source_html + page_html

        # 创建 RSS <item>
        item_elem = ET.SubElement(channel, "item")
        ET.SubElement(item_elem, "title").text = title_text
        ET.SubElement(item_elem, "link").text = source_url
        content_elem = ET.SubElement(item_elem, "{http://purl.org/rss/1.0/modules/content/}encoded")
        content_elem.text = page_html
        pub_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item_elem, "pubDate").text = pub_date

    rss_xml = ET.tostring(rss, encoding="utf-8", method="xml").decode("utf-8")
    return rss_xml

# ================================
# 7. 主函数：查询、生成并写入 RSS (Main function)
# ================================
def main():
    items = query_notion_database()
    rss_content = generate_rss(items)
    # 确保 docs 文件夹存在，否则请提前创建
    with open("docs/rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)
    print("RSS generated and written to docs/rss.xml")

if __name__ == "__main__":
    main()
