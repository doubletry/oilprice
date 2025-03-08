import requests
from bs4 import BeautifulSoup
from loguru import logger


def parse_oil_price(url):
    response = requests.get(url)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    rightTop_content = soup.find(id="rightTop")
    if rightTop_content:
        first_div = rightTop_content.find("div")
        if first_div:
            title = ""
            for element in first_div.contents:
                if element.name == "br":
                    break
                title += str(element)

            content = soup.find("div", id="rightTop").find_all("div")[1].text.strip()

            if not content or not title:
                logger.error("未找到标题或内容")
                return None

            return {"title": title, "content": content}
    else:
        logger.error("未找到rightTop")
        return None
