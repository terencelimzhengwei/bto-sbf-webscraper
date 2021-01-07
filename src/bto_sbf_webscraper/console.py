import os
import logging

import click
import pandas as pd

from bto_sbf_webscraper.scraper import (
    get_available_flats,
    scrape,
)

from . import __version__

os.environ["WDM_LOG_LEVEL"] = str(logging.WARNING)


@click.command()
@click.option(
    "--selection_type",
    "-s",
    default="BTO",
    help="Choose between BTO / SBF / OBF",
    show_default=True,
)
@click.option(
    "--launch_date",
    "-l",
    help="Choose your launch date",
    show_default=True,
)
@click.option(
    "--town",
    "-t",
    help="Choose your town",
    show_default=True,
)
@click.option(
    "--flat_type",
    "-f",
    help="Choose your flat type (2, 3, 4, 5, All)",
    show_default=True,
)
@click.version_option(version=__version__)
def main(selection_type, launch_date, town, flat_type):
    """Test Project"""
    if selection_type and (not launch_date and not town and not flat_type):
        flats_available = get_available_flats(selection_type)
        print_flats(flats_available)
        if flats_available:
            launch_date = get_launch_date(flats_available)
            flat_type = get_flat_types(launch_date, flats_available)
            town = get_town(launch_date, flat_type, flats_available)
            data = scrape(selection_type, launch_date, flat_type, town)
            file_name = f"{selection_type}_{launch_date}_{flat_type if flat_type else 'All'} Room_{town if town else 'All'}.csv".replace(
                "/", "-"
            )
            pd.DataFrame(data).to_csv(file_name, index=None)
            click.echo(f"Successfully saved to {file_name}")
    else:
        data = scrape(selection_type, launch_date, flat_type, town)
        file_name = f"{selection_type}_{launch_date}_{flat_type if flat_type else 'All'} Room_{town if town else 'All'}.csv".replace(
            "/", "-"
        )
        pd.DataFrame(data).to_csv(file_name, index=None)
        click.echo(f"Successfully saved to {file_name}")


def get_launch_date(flats_available):
    launches = [x["launch_date"] for x in flats_available]
    launch_date = click.prompt(
        f"Which launch date are you interested in ({', '.join(launches)})?", type=str
    )
    while launch_date not in launches:
        launch_date = click.prompt(
            "Please try again. Which launch date are you interested in?", type=str
        )
    return launch_date


def get_flat_types(launch_date, flats_available):
    launch = [x for x in flats_available if x["launch_date"] == launch_date][0]
    flat_types = []
    for town in launch["towns"]:
        for ft in town["flat_types"]:
            flat_types.append(ft["flat_type"][0])
    flat_types = sorted(list(set(flat_types))) + ["All"]
    flat_type = click.prompt(
        f"How many rooms are you looking at " f"({', '.join(flat_types)})?", type=str
    )
    while flat_type not in flat_types:
        flat_type = click.prompt(
            f"Please try again. "
            f"How many rooms are you looking at "
            f"({', '.join(flat_types)})?",
            type=str,
        )
    flat_type = None if flat_type.lower() == "all" else flat_type
    return flat_type


def get_town(launch_date, flat_type, flats_available):
    launch = [x for x in flats_available if x["launch_date"] == launch_date][0]
    towns = []
    for town in launch["towns"]:
        for ft in town["flat_types"]:
            if (f"{flat_type}-Room" in ft["flat_type"]) or (not flat_type):
                towns.append(town["town"])
                break
    towns = sorted(list(set(towns))) + ["All"]
    town = click.prompt(
        f"Which town are you interested in " f"({', '.join(towns)})?", type=str
    )
    while town.lower() not in [x.lower() for x in towns]:
        town = click.prompt(
            f"Please try again. "
            f"Which town are you interested in "
            f"({', '.join(towns)})?",
            type=str,
        )
    town = None if town.lower() == "all" else flat_type
    return town


def print_flats(flat_object):
    if len(flat_object) == 0:
        click.secho("No flats available ):", fg="red")
    for launch in flat_object:
        click.secho(launch["launch_date"], fg="green")
        towns = launch["towns"]
        for town in towns:
            click.secho(town["town"], fg="yellow")
            flat_types = town["flat_types"]
            for flat_type in flat_types:
                text = (
                    f"{flat_type['flat_type']} - "
                    f"{flat_type['units_available']} units - "
                    f"Malay : {flat_type['malay_quota']}, "
                    f"Chinese : {flat_type['chinese_quota']}, "
                    f"Indian : {flat_type['indian_others_quota']}"
                )
                click.secho(text, fg="white")
        click.echo()
