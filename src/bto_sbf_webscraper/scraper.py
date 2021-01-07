import re
from copy import deepcopy
from time import sleep
from urllib.parse import unquote

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


def get_available_flats(selection_type="OBF"):
    url = f"https://services2.hdb.gov.sg/webapp/BP13AWFlatAvail/BP13SEstateSummary?sel={selection_type}"
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    # driver = webdriver.Chrome(ChromeDriverManager().install())
    driver.get(url)
    html = BeautifulSoup(
        driver.execute_script("return document.documentElement.innerHTML"),
        features="html.parser",
    )
    launches = (
        html.find("form")
        .find_all("div", {"class": "row"}, recursive=False)[2]
        .find_all("div", recursive=False)[0]
        .find_all("div", recursive=False)
    )
    flats_dict = []
    for launch in launches:
        launch_dict = {}
        launch_dict["launch_date"] = launch.find("h4", recursive=False).text
        towns = launch.find_all("div", recursive=False)
        launch_dict["towns"] = []
        for town in towns:
            town_dict = {}
            town_dict["town"] = town.find("h5").text
            flat_types = town.find("tbody").find_all("tr")
            town_dict["flat_types"] = []
            for flat_type in flat_types:
                flat_dict = {}
                columns = flat_type.find_all("td")
                if len(columns) == 1:
                    continue
                flat_dict["flat_type"] = columns[0].text
                flat_link = columns[0].find("a").get("href")
                p = re.compile('(\\/.+=.?)\\"')
                flat_path = p.findall(flat_link)[0]
                flat_dict["flat_link"] = "https://services2.hdb.gov.sg" + flat_path
                flat_dict["units_available"] = columns[1].text
                flat_dict["malay_quota"] = columns[2].text
                flat_dict["chinese_quota"] = columns[3].text
                flat_dict["indian_others_quota"] = columns[4].text
                town_dict["flat_types"].append(flat_dict)
            launch_dict["towns"].append(town_dict)
        flats_dict.append(launch_dict)
    driver.close()
    return flats_dict


def scrape_link(driver, flat_link):
    p = re.compile("Town=(.+?)&")
    town = unquote(p.findall(flat_link)[0])
    success = False
    while not success:
        try:
            driver.get(flat_link)
            html = BeautifulSoup(
                driver.execute_script("return document.documentElement.innerHTML"),
                features="html.parser",
            )
            links = [
                a.find("div").get("onclick") for a in html.find("table").find_all("td")
            ]
            success = True
        except Exception:
            sleep(5)
            pass
    final_data = []
    index = 0
    length = len(links)
    town = unquote(re.compile("Town=(.+?)&").findall(flat_link)[0])
    flat = unquote(re.compile("Flat=(.+?)&").findall(flat_link)[0])
    for link in links:
        index = index + 1
        driver.execute_script(link)
        sleep(10)
        html_doc = driver.execute_script("return document.documentElement.innerHTML")
        doc = BeautifulSoup(html_doc, features="html.parser")
        prices = [a for a in doc.find_all("span", class_="tooltip") if "$" in a.text]
        if len(prices) > 0:
            block_details = doc.find("div", {"id": "blockDetails"}).find_all(
                "div", {"class": "columns"}
            )
            temp_list = []
            for x in block_details:
                text = x.text.strip().replace("\xa0", " ")
                temp_list.append(text)
                if "Malay-" in text:
                    break
            initial_dict = {}
            initial_dict["Town"] = town
            initial_dict["Flat Type"] = flat
            it = iter(temp_list)
            initial_dict = {**initial_dict, **dict(zip(it, it))}

        for price in prices:
            temp_data = price.get("title").split("____________________")
            initial_dict["Price"] = temp_data[0].replace("<br>", "\n").strip()
            initial_dict["Size"] = (
                temp_data[1].strip().replace("\xa0", " ").replace("<br>", "")
            )
            initial_dict["Unit"] = price.get("data-selector")
            print(
                f"{town} - {flat} - {initial_dict['Block']} - {initial_dict['Unit']}: {index} / {length}"
            )
            final_data.append(deepcopy(initial_dict))

    return final_data


def get_links_to_scrape(selection_type, launch_date, flat_type=None, town=None):
    flats_available = get_available_flats(selection_type)
    links = []
    if flats_available:
        launch_list = [x for x in flats_available if x["launch_date"] == launch_date]
        if len(launch_list) == 1:
            launch = launch_list[0]
            towns = (
                [x for x in launch["towns"] if x["town"] == town]
                if town
                else launch["towns"]
            )
            for t in towns:
                for f in t["flat_types"]:
                    if (f"{flat_type}-Room" in f["flat_type"]) or not flat_type:
                        links.append(f["flat_link"])

    return links


def scrape_links(links):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    # driver = webdriver.Chrome(ChromeDriverManager().install())
    data = []
    index = 0
    length = len(links)
    for link in links:
        index = index + 1
        town = unquote(re.compile("Town=(.+?)&").findall(link)[0])
        flat = unquote(re.compile("Flat=(.+?)&").findall(link)[0])
        print(f"{town} - {flat} : {index} / {length}")
        flat_data = scrape_link(driver, link)
        data = data + flat_data
    driver.close()
    return data


def scrape(selection_type, launch_date, flat_type=None, town=None):
    print("Starting to scrape for...")
    print(
        f"Type : {selection_type}, Launch Date : {launch_date}, "
        f"Flat Type : {flat_type if flat_type else 'All'} Room, "
        f"Town : {town if town else 'All'}"
    )
    links = get_links_to_scrape(selection_type, launch_date, flat_type, town)
    data = scrape_links(links)
    return data
