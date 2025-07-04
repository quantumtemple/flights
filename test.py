import asyncio

from fast_flights import FlightData, Passengers, create_filter, get_flights_from_filter

filter = create_filter(
    flight_data=[
        # Include more if it's not a one-way trip
        FlightData(
            date="2025-07-20",  # Date of departure
            from_airport="SIN",  # Departure (airport)
            to_airport="CAN",  # Arrival (airport)
        )
    ],
    trip="one-way",  # Trip type
    passengers=Passengers(
        adults=1, children=0, infants_in_seat=0, infants_on_lap=0
    ),  # Passengers
    seat="economy",  # Seat type
    max_stops=0,  # Maximum number of stops
)
print(filter.as_b64().decode("utf-8"))


async def main():
    flights = await get_flights_from_filter(
        filter,
        mode="common",
        language="zh-CN",
        currency="CNY",
        sort_by="price",
        gl="CN",
    )
    for flight in flights.flights:
        print(flight)


asyncio.run(main())
