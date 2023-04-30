import typing as tp
import requests
import json

from pprint import pprint
import asyncio
import aiohttp

url = 'https://api.open-meteo.com/v1/forecast'


class APIRequest:
    def __init__(self, url, params):
        self.url = url
        self.params = params


class APIResponse:
    def __init__(self, status, content, timeout):
        self.status = status
        self.content = content
        self.timeout = timeout


def perform_request(url: str, params: tp.Dict[str, tp.Any]) -> None:
    params_str = (
        ""
        if not params else
        '&'.join(f"{k}={','.join(v) if isinstance(v, list) else v}" for (k, v) in params.items())
    )
    url_str = (
        url
        if not params_str else
        f"{url}?{params_str}"
    )

    status, content, timeout = None, None, False

    try:
        resp = requests.get(url_str, timeout=1)
        status = resp.status_code
        content = json.loads(resp.content)
    except requests.exceptions.ReadTimeout as e:
        timeout = True

    return APIResponse(status, content, timeout)


def test_functional():
    reqs = [
        APIRequest(
            url,
            {
                'latitude': 59.94,
                'longitude': 30.31,
                'hourly': 'temperature_2m',
            },
        ),
        APIRequest(
            url,
            {
                'latitude': 59.94,
                'longitude': 30.31,
                'hourly': ['temperature_2m', 'relativehumidity_2m'],
            }
        ),
        APIRequest(
            url,
            {
                'latitude': 59.94,
                'longitude': 30.31,
                'hourly': 'temperature_2m',
                'forecast_days': 5,
            }
        ),
        APIRequest(
            url,
            {
                'latitude': 59.94,
                'longitude': 30.31,
                'daily': 'temperature_2m_max',
                'timezone': 'GMT',
                'forecast_days': 5,
            }
        ),
    ]
    
    reses = [perform_request(r.url, r.params) for r in reqs]

    assert not any([res.timeout for res in reses]), "Some of the requests timed out"
    assert all([res.status == 200 for res in reses]), "Some of the requests did not finish with OK"
    assert reses[0].status == 200 and len(reses[0].content['hourly']['time']) == len(reses[0].content['hourly']['temperature_2m']), "Data and time lists should have the same length"
    assert reses[1].status == 200 and len(reses[1].content['hourly']['temperature_2m']) == len(reses[1].content['hourly']['relativehumidity_2m']), "Data lists should have the same length"
    assert reses[2].status == 200 and len(reses[2].content['hourly']['temperature_2m']) == 120, "Hourly data list length should have the length of the amount of days times 24"
    assert reses[2].status == 200 and len(reses[3].content['daily']['temperature_2m_max']) == 5, "Daily data list length should have the length of the amount of days"


async def stress_get(url, session, timeout):
    try:
        async with session.get(url=url, timeout=timeout) as response:
            resp = await response.read()
    except Exception as e:
        return None

    return resp

async def stress(url, amount, timeout):
    async with aiohttp.ClientSession() as session:
        reses = await asyncio.gather(*[stress_get(url, session, timeout) for _ in range(amount)])

    assert not any([res is None for res in reses]), f"One of {amount} responses timed out after {timeout} seconds"

def test_stress():
    req = APIRequest(
        url,
        {
            'latitude': 59.94,
            'longitude': 30.31,
            'hourly': 'temperature_2m',
        },
    )

    asyncio.run(stress(url, 10, 0.5))   # SHORT STRESS
    asyncio.run(stress(url, 100, 1))    # MODERATE STRESS
    asyncio.run(stress(url, 1000, 5))   # LONG STRESS


def test_negative():
    reqs = [
        APIRequest(                     # INVALID COORDINATES
            url,
            {
                'latitude': 96,
                'longitude': 420
            },
        ),
        APIRequest(                     # INVALID VALUE
            url,
            {
                'latitude': 59.94,
                'longitude': 30.31,
                'hourly': 'kek'
            },
        ),
        APIRequest(                     # INVALID KEY
            url,
            {
                'latitude': 59.94,
                'longitude': 30.31,
                'kek': 'lul'
            },
        ),
        APIRequest(                     # NO PARAMETERS
            url,
            {},
        )
    ]

    reses = [perform_request(r.url, r.params) for r in reqs]

    assert not all([res.status == 400 for res in reses]), "Some of the requests did not finish with Bad Request"
