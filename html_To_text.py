from bs4 import BeautifulSoup

html = open(".html", encoding="utf-8").read()
soup = BeautifulSoup(html, "html.parser")

texto = soup.get_text()

print(texto)