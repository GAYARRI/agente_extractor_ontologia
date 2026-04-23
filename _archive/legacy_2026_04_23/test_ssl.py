import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://visitasevilla.es/"

try:
    r = requests.get(
        url,
        timeout=15,
        verify=False,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    print("OK")
    print("status:", r.status_code)
    print("final_url:", r.url)
    print(r.text[:300])
except Exception as e:
    print("ERROR:", repr(e))