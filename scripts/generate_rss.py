import os
import requests
import datetime
import xml.etree.ElementTree as ET

# ================================
# 1. 配置 Notion API 参数
# ================================
NOTION_TOKEN = os.getenv("NOTION_TOKEN")        # 从环境变量获取 Notion 集成令牌
DATABASE_ID = os.getenv("DATABASE_ID")          # 从环境变量获取数据库 ID

# Notion 数据库查询 URL
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
    查询 Notion 数据库中的所有条目，不进行额外过滤（这样即使 URL、Type、Publish Date、Status 为空也会返回）。
    若需要过滤可修改 data 参数。
    """
    data = {
        "page_size": 100
    }
    response = requests.post(NOTION_API_URL, headers=HEADERS, json=data)
    response.raise_for_status()
    data_json = response.json()
    # 可调试：打印返回条目数
    # print("Number of items returned:", len(data_json["results"]))
    return data_json["results"]

# ================================
# 3. 获取 Notion 页面块内容
# ================================
def get_page_blocks(page_id):
    """
    根据页面 ID，通过 Notion API 获取该页面的所有块内容。
    调用 /v1/blocks/{block_id}/children 接口。
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
    遍历 Notion 页面块，将不同类型的块转换为 HTML 格式。
    支持：
      - paragraph：段落文本（处理加粗、斜体、链接）
      - heading_1：标题1
      - heading_2：标题2
      - file：文件块（例如 PDF），输出下载链接
    其他类型可根据需要扩展。
    """
    html_fragments = []
    for block in blocks:
        block_type = block.get("type")
        # 处理段落文本
        if block_type == "paragraph":
            paragraph_text = ""
            for text_item in block["paragraph"]["rich_text"]:
                text_content = text_item.get("plain_text", "")
                annotations = text_item.get("annotations", {})
                # 添加简单样式：加粗、斜体
                if annotations.get("bold"):
                    text_content = f"<strong>{text_content}</strong>"
                if annotations.get("italic"):
                    text_content = f"<em>{text_content}</em>"
                # 如果有链接则转换为 <a> 标签
                if text_item.get("text", {}).get("link"):
                    link_url = text_item["text"]["link"].get("url", "#")
                    text_content = f'<a href="{link_url}">{text_content}</a>'
                paragraph_text += text_content
            html_fragments.append(f"<p>{paragraph_text}</p>")

        # 处理标题 1
        elif block_type == "heading_1":
            heading_text = "".join([t.get("plain_text", "") for t in block["heading_1"]["rich_text"]])
            html_fragments.append(f"<h1>{heading_text}</h1>")
        
        # 处理标题 2
        elif block_type == "heading_2":
            heading_text = "".join([t.get("plain_text", "") for t in block["heading_2"]["rich_text"]])
            html_fragments.append(f"<h2>{heading_text}</h2>")
        
        # 处理文件块（例如 PDF 文件）
        elif block_type == "file":
            file_info = block["file"]
            file_url = ""
            # 判断文件是外部链接还是 Notion 内部上传
            if "external" in file_info:
                file_url = file_info["external"].get("url", "")
            elif "file" in file_info:
                file_url = file_info["file"].get("url", "")
            # 获取文件名称，若有的话
            file_name = block.get("name", "Download File")
            html_fragments.append(f'<p><a href="{file_url}" download>{file_name}</a></p>')
        
        # 可以扩展处理其他块类型，例如 bulleted_list_item, to_do 等
        
    return "\n".join(html_fragments)

# ================================
# 5. 生成 RSS XML
# ================================
def generate_rss(items):
    """
    遍历 Notion 数据库条目，为每个条目调用 get_page_blocks 和 convert_blocks_to_html 获取富文本内容，
    并生成 RSS 的 <item> 标签。
    
    每个 <item> 包括：
      - <title>：使用 Notion 的标题属性（请确保数据库中标题列名称为 "Title"，否则修改此处）
      - <link>：可自定义，例如 Notion 页面链接（这里示例拼接 Notion 页面 URL）
      - <description>：使用 <![CDATA[...]]> 包裹生成的 HTML 内容
      - <content:encoded>：同样输出 HTML（需要添加命名空间）
      - <pubDate>：发布时间（使用当前系统时间，可根据需要改为 Notion 中的日期）
    """
    # 设置 RSS 根节点，并添加 content 命名空间
    rss = ET.Element("rss", version="2.0", attrib={"xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Daily Reading"
    ET.SubElement(channel, "link").text = "https://yourusername.github.io/notion-to-rss"
    ET.SubElement(channel, "description").text = "Generated from Notion."

    for item in items:
        properties = item.get("properties", {})
        # 获取标题（请确保 Notion 中的标题列名称为 "Title"）
        title_text = "No Title"
        if "Title" in properties:
            title_data = properties["Title"]["title"]
            if title_data:
                title_text = title_data[0].get("plain_text", "No Title")
        
        # 使用 Notion 数据库条目的 id 作为页面 id
        page_id = item.get("id")
        
        # 获取该页面的块内容，并转换为 HTML
        blocks = get_page_blocks(page_id)
        page_html = convert_blocks_to_html(blocks)

        # 创建 RSS <item> 标签
        item_elem = ET.SubElement(channel, "item")
        ET.SubElement(item_elem, "title").text = title_text
        # 此处构造一个链接示例，可修改为 Notion 页面实际链接
        ET.SubElement(item_elem, "link").text = "https://www.notion.so/" + page_id.replace("-", "")
        # 输出描述，使用 <![CDATA[...]]> 包裹 HTML 富文本内容
        description_elem = ET.SubElement(item_elem, "description")
        description_elem.text = f"<![CDATA[{page_html}]]>"
        # 同时使用 content:encoded 输出完整内容
        content_elem = ET.SubElement(item_elem, "{http://purl.org/rss/1.0/modules/content/}encoded")
        content_elem.text = f"<![CDATA[{page_html}]]>"
        # 设置发布日期，采用 RFC-822 格式。此处用当前时间作为示例。
        pub_date = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
        ET.SubElement(item_elem, "pubDate").text = pub_date

    # 将整个 XML 树转换为字符串
    rss_xml = ET.tostring(rss, encoding="utf-8", method="xml").decode("utf-8")
    return rss_xml

# ================================
# 6. 主函数
# ================================
def main():
    # 查询 Notion 数据库中的所有记录
    items = query_notion_database()
    # 生成 RSS XML 内容
    rss_content = generate_rss(items)
    # 将 RSS 写入到 docs/rss.xml（确保你的仓库中存在 docs 文件夹，并在 GitHub Pages 设置中选择 docs）
    with open("docs/rss.xml", "w", encoding="utf-8") as f:
        f.write(rss_content)
    print("RSS generated and written to docs/rss.xml")

if __name__ == "__main__":
    main()
