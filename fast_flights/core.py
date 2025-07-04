from typing import Annotated, List, Literal, Optional
from urllib.parse import urlencode

from selectolax.lexbor import LexborHTMLParser, LexborNode

from .extract_data import get_js_callback_data
from .fallback_playwright import fallback_playwright_fetch
from .filter import TFSData
from .flights_impl import FlightData, Passengers
from .primp import AsyncClient, Response
from .schema import Flight, Result


async def fetch(params: dict) -> Response:
    client = AsyncClient(impersonate="chrome_126", verify=False)
    # print out the url
    print(f"https://www.google.com/travel/flights?{urlencode(params)}")
    res = await client.get("https://www.google.com/travel/flights", params=params)

    # save res.text to file
    # with open("res.html", "w") as f:
    #     f.write(res.text)

    assert res.status_code == 200, f"{res.status_code} Result: {res.text_markdown}"
    return res


async def get_flights_from_filter(
    filter: TFSData,
    currency: Annotated[str, "e.g. USD, CNY, HKD, GBP, EUR"] = "USD",
    *,
    mode: Literal["common", "fallback", "force-fallback", "local"] = "common",
    language: Annotated[str, "e.g. en, zh-CN, es"] = "en",
    sort_by: Literal[
        "top_flights", "price", "departure_time", "arrival_time", "duration"
    ] = "top_flights",
    gl: Annotated[str, "e.g. US, CN, HK, GB, FR"] = "US",
) -> Result:
    data = filter.as_b64()

    sort_by_map = {
        "top_flights": "EggIARABIAIoByIA",
        "price": "EggIAhABIAIoByIA",
        "departure_time": "EggIAxABIAIoByIA",
        "arrival_time": "EggIBBABIAIoByIA",
        "duration": "EggIBRABIAIoByIA",
    }

    params = {
        "tfs": data.decode("utf-8"),
        "hl": language,
        "tfu": sort_by_map[sort_by],
        "curr": currency,
        "gl": gl,
    }

    if mode in {"common", "fallback"}:
        try:
            res = await fetch(params)
        except AssertionError as e:
            if mode == "fallback":
                res = fallback_playwright_fetch(params)
            else:
                raise e

    elif mode == "local":
        from .local_playwright import local_playwright_fetch

        res = local_playwright_fetch(params)

    else:
        res = fallback_playwright_fetch(params)

    try:
        return parse_response(res)
    except RuntimeError as e:
        if mode == "fallback":
            return await get_flights_from_filter(filter, mode="force-fallback")
        raise e


async def get_flights(
    *,
    flight_data: List[FlightData],
    trip: Literal["round-trip", "one-way", "multi-city"],
    passengers: Passengers,
    seat: Literal["economy", "premium-economy", "business", "first"],
    fetch_mode: Literal["common", "fallback", "force-fallback", "local"] = "common",
    max_stops: Optional[int] = None,
) -> Result:
    return await get_flights_from_filter(
        TFSData.from_interface(
            flight_data=flight_data,
            trip=trip,
            passengers=passengers,
            seat=seat,
            max_stops=max_stops,
        ),
        mode=fetch_mode,
    )


def parse_response(
    r: Response, *, dangerously_allow_looping_last_item: bool = False
) -> Result:
    class _blank:
        def text(self, *_, **__):
            return ""

        def iter(self):
            return []

    blank = _blank()

    def safe(n: Optional[LexborNode]):
        return n or blank

    parser = LexborHTMLParser(r.text)
    parsed_script = parser.css_first("script[class='ds:1']")
    raw_data = get_js_callback_data(parsed_script.text())

    raw_data = (raw_data[2][0] if raw_data[2] else []) + (
        raw_data[3][0] if raw_data[3] else []
    )

    flights = []
    flight_ids = set()

    for i, fl in enumerate(parser.css('div[jsname="IWWDBc"], div[jsname="YdtKid"]')):
        is_best_flight = i == 0

        for item in fl.css("ul.Rk10dc li")[
            : (None if dangerously_allow_looping_last_item or i == 0 else -1)
        ]:
            data_id = item.css_first("div").attributes.get("data-id")
            if data_id is None:
                continue
            if data_id in flight_ids:
                continue
            flight_ids.add(data_id)

            flight_no = []
            aircraft_model = []
            for raw_data_row in raw_data:
                if data_id in str(raw_data_row):
                    flights_info = raw_data_row[0][2]
                    for flight_info in flights_info:
                        flight_no.append(flight_info[22][0] + flight_info[22][1])
                        aircraft_model.append(flight_info[17])
                    break

            # Flight name
            name = safe(item.css_first("div.sSHqwe.tPgKwe.ogfYpf span")).text(
                strip=True
            )

            # Get departure & arrival time
            dp_ar_node = item.css("span.mv1WYe div")
            try:
                departure_time = dp_ar_node[0].text(strip=True)
                arrival_time = dp_ar_node[1].text(strip=True)
            except IndexError:
                # sometimes this is not present
                departure_time = ""
                arrival_time = ""

            # Get arrival time ahead
            time_ahead = safe(item.css_first("span.bOzv6")).text()

            # Get duration
            duration = safe(item.css_first("li div.Ak5kof div")).text()

            # Get flight stops
            stops = safe(item.css_first(".BbR8Ec .ogfYpf")).text()

            # Get delay
            delay = safe(item.css_first(".GsCCve")).text() or None

            # Get prices
            price = safe(item.css_first(".YMlIz.FpEdX")).text() or "0"

            # get logo
            logo_style = safe(item.css_first("div.EbY4Pc.P2UJoe")).attributes.get(
                "style", ""
            )
            logo_default = None
            logo_dark = None
            if logo_style:
                import re

                match_default = re.search(
                    r"--travel-primitives-themeable-image-default:\s*url\(([^)]+)\)",
                    logo_style,
                )
                match_dark = re.search(
                    r"--travel-primitives-themeable-image-dark:\s*url\(([^)]+)\)",
                    logo_style,
                )
                if match_default:
                    logo_default = match_default.group(1)
                if match_dark:
                    logo_dark = match_dark.group(1)
            logo = {"default": logo_default, "dark": logo_dark}

            # Stops formatting
            # try:
            #     stops_fmt = 0 if stops == "Nonstop" else int(stops.split(" ", 1)[0])
            # except ValueError:
            #     stops_fmt = "Unknown"

            flights.append(
                {
                    "is_best": is_best_flight,
                    "name": name,
                    "flight_number": ", ".join(flight_no),
                    "aircraft_model": ", ".join(aircraft_model),
                    "departure": " ".join(departure_time.split()),
                    "arrival": " ".join(arrival_time.split()),
                    "arrival_time_ahead": time_ahead,
                    "duration": duration,
                    "stops": stops,
                    "delay": delay,
                    "price": price,
                    "logo": logo,
                }
            )

    current_price = safe(parser.css_first("span.gOatQ")).text()
    if not flights:
        raise RuntimeError("No flights found:\n{}".format(r.text_markdown))

    return Result(current_price=current_price, flights=[Flight(**fl) for fl in flights])  # type: ignore
