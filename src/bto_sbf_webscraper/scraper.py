import re
from time import sleep
from urllib.parse import unquote

import click
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


def get_available_flats(selection_type="OBF"):
    url = f"https://services2.hdb.gov.sg/webapp/BP13AWFlatAvail/BP13SEstateSummary?sel={selection_type}"
    chrome_options = set_chrome_options()
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


def get_list_by_id(driver, id):
    """Get list of values for Towns or Flats

    Args:
        driver (webdriver): Selenium Webdriver
        id (str): 'Town' or 'Flat'

    Returns:
        list (str): Returns list of values that can be selected
    """
    try:
        flat_list = [
            a.get_attribute("value")
            for a in driver.find_element_by_id(id).find_elements_by_tag_name("option")
        ]
        return flat_list
    except Exception:
        return []


def get_block_links(driver, flat_link):
    """Get block links that needs to be scraped

    Args:
        driver (webdriver): Selenium Webdriver
        flat_link (str): url of the flat link that needs to be scraped to get the block links

    Returns:
        list (str): List of javascript snippets that needs to be executed
    """
    success = False
    while not success:
        try:
            driver.get(flat_link)
            links = [
                a.find_element_by_tag_name("div").get_attribute("onclick")
                for a in driver.find_element_by_tag_name(
                    "table"
                ).find_elements_by_tag_name("td")
            ]
            success = True
            return links
        except Exception:
            sleep(5)
            pass


def get_value_by_id(driver, id):
    """Returns the value of the object in the html doc

    Args:
        driver (webdriver): Selenium Webdriver
        id (str): HTML id that you want to retrieve

    Returns:
        str: Value of the HTML element that contains the ID
    """
    try:
        return driver.find_element_by_id(id).get_attribute("value")
    except Exception:
        return None


def get_block_details(driver):
    """Get block details (Block, Street, Ethnic Quota, Delivery Date etc.)

    Args:
        driver (webdriver): Selenium Webdriver

    Returns:
        dict: Dictionary containing the details of the block
    """
    block_details = driver.find_elements_by_xpath(
        "//div[contains(@id, 'blockDetails')]"
        "/div[contains(@class, 'row')]"
        "/div[contains(@class, 'columns')]"
    )
    data = []
    for block in block_details:
        text = block.text.strip().replace("\xa0", " ")
        data.append(text)
        if "Malay-" in text:
            break
    it = iter(data)
    return dict(zip(it, it))


def process_block(driver, link):
    """Return the block details and unit details of the block that needs to be scraped

    Args:
        driver (webdriver): Selenium Webdriver
        link (str): Javascript code that needs to be executed to enter the page

    Returns:
        list (dict): Returns list of dictionaries containing details of the block and units
    """
    success = False
    while not success:
        try:
            initial_dict = {}
            driver.execute_script(link)
            sleep(5)
            initial_dict["Town"] = get_value_by_id(driver, "Town")
            initial_dict["Flat"] = get_value_by_id(driver, "Flat")
            unit_details = get_unit_details(driver)

            if unit_details:
                block_details = get_block_details(driver)
                final_data = [
                    {**initial_dict, **block_details, **x} for x in unit_details
                ]
                success = True
                return final_data
        except Exception:
            sleep(5)
            pass


def get_unit_details(driver):
    """Get unit details such as price, unit number and size of the flat

    Args:
        driver (webdriver): Selenium webdriver

    Returns:
        dict : Returns dictionary containing unit details
    """
    unit_details = [
        a
        for a in driver.find_elements_by_xpath("//span[contains(@class, 'tooltip')]")
        if "$" in a.get_attribute("title")
    ]
    data = []
    for unit in unit_details:
        unit_dict = {}
        unit_dict["Unit"] = unit.get_attribute("data-selector")
        title = unit.get_attribute("title").replace("\xa0", " ")
        unit_dict["Price"] = re.compile("(\\$.+?)<").findall(title)[0]
        unit_dict["Size"] = re.compile(">(\\d.+Sqm)").findall(title)[0]
        data.append(unit_dict)
    return data


def scrape_link(driver, flat_link):
    """Scrapes the given HDB flat link

    Args:
        driver (webdriver): Selenium Webdriver
        flat_link (str): URL of the flat link that needs to be scraped

    Returns:
        list (dict): Returns list of dictionaries containing all the blocks and units in the flat link
    """
    block_links = get_block_links(driver, flat_link)
    final_data = []
    town = unquote(re.compile("Town=(.+?)&").findall(flat_link)[0])
    flat = unquote(re.compile("Flat=(.+?)&").findall(flat_link)[0])
    with click.progressbar(
        block_links,
        label=f"{town} - {flat} Room",
        show_pos=True,
        show_eta=False,
    ) as linkss:
        for link in linkss:
            data = process_block(driver, link)
            final_data = final_data + data

    return final_data


def get_links_to_scrape(selection_type, launch_date, flat_type=None, town=None):
    """Retrieves the list of links that needs to be scraped from the HDB site

    Args:
        selection_type (str): SBF / OBF / BTO
        launch_date (str): Date of ballot / Sales Launch
        flat_type (str, optional): Number of rooms of flat. Defaults to None.
        town (str, optional): Town of flat. Defaults to None.

    Returns:
        list (str): Returns a list of urls that needs to be scraped
    """
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
    """Scrape all the links provided

    Args:
        links (str): Links that needs to be scraped from HDB site

    Returns:
        list (dict): List of dictionaries containing all the data for the HDB
    """
    chrome_options = set_chrome_options()
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    # driver = webdriver.Chrome(ChromeDriverManager().install())
    data = []
    click.secho("Processing Blocks", fg="green")
    for link in links:
        flat_data = scrape_link(driver, link)
        data = data + flat_data
    driver.close()
    return data


def scrape(selection_type, launch_date, flat_type=None, town=None):
    """Retrieves all the links to scrape and scrapes them

    Args:
        selection_type (str): SBF / OBF / BTO
        launch_date (str): Date of ballot / Sales Launch
        flat_type (str, optional): Number of rooms of flat. Defaults to None.
        town (str, optional): Town of flat. Defaults to None.

    Returns:
        list (dict): Returns list of dictionaries containing all the blocks and units for all links
    """
    click.secho("\nStarting to scrape for...", fg="yellow")
    click.secho(
        f"Type : {selection_type}, Launch Date : {launch_date}, "
        f"Flat Type : {flat_type if flat_type else 'All'} Room, "
        f"Town : {town if town else 'All'}",
    )
    links = get_links_to_scrape(selection_type, launch_date, flat_type, town)
    data = scrape_links(links)
    return data


def set_chrome_options():
    """Sets chrome options for Selenium.
    Chrome options for headless browser is enabled.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_prefs = {}
    chrome_options.experimental_options["prefs"] = chrome_prefs
    chrome_prefs["profile.default_content_settings"] = {"images": 2}
    return chrome_options
