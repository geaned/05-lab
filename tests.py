import aiohttp
import asyncio
import json
import requests
import typing as tp

url = 'https://api.open-meteo.com/v1/forecast'


class APIResponse:
    def __init__(self, status, content, timeout):
        self.status = status
        self.content = content
        self.timeout = timeout


class APIRequest:
    def __init__(self, url: str, params: tp.Dict[str, tp.Any]) -> APIResponse:
        self.url = url
        self.params = params
    
    def perform_request(self) -> None:
        url_str = self.make_full_url()

        status, content, timeout = None, None, False

        try:
            resp = requests.get(url_str, timeout=2)
            status = resp.status_code
            content = json.loads(resp.content)
        except requests.exceptions.ReadTimeout as e:
            timeout = True

        return APIResponse(status, content, timeout)

    def make_full_url(self) -> str:
        params_str = (
            ""
            if not self.params else
            '&'.join(f"{k}={','.join(v) if isinstance(v, list) else v}" for (k, v) in self.params.items())
        )
        url_str = (
            self.url
            if not params_str else
            f"{self.url}?{params_str}"
        )
        return url_str


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
    
    reses = [r.perform_request() for r in reqs]

    assert all([not res.timeout for res in reses]), "Some of the requests timed out (try running the tests again)"
    assert all([res.status == 200 for res in reses]), "Some of the requests did not finish with OK"
    assert reses[0].status == 200 and len(reses[0].content['hourly']['time']) == len(reses[0].content['hourly']['temperature_2m']), "Data and time lists should have the same length"
    assert reses[1].status == 200 and len(reses[1].content['hourly']['temperature_2m']) == len(reses[1].content['hourly']['relativehumidity_2m']), "Data lists should have the same length"
    assert reses[2].status == 200 and len(reses[2].content['hourly']['temperature_2m']) == 120, "Hourly data list length should have the length of the amount of days times 24"
    assert reses[2].status == 200 and len(reses[3].content['daily']['temperature_2m_max']) == 5, "Daily data list length should have the length of the amount of days"


async def stress_get(url, session, timeout):
    try:
        async with session.get(url=url, timeout=timeout) as response:
            resp = await response.read()
    except asyncio.exceptions.TimeoutError:
        return None

    return resp

async def stress(url, amount, timeout):
    async with aiohttp.ClientSession() as session:
        reses = await asyncio.gather(*[stress_get(url, session, timeout) for _ in range(amount)])

    assert all([res is not None for res in reses]), f"One of {amount} responses timed out after {timeout} seconds"

def test_stress():
    req = APIRequest(
        url,
        {
            'latitude': 59.94,
            'longitude': 30.31,
            'hourly': 'temperature_2m',
        },
    )
    url_str = req.make_full_url()

    asyncio.run(stress(url_str, 10, 0.5))   # SHORT STRESS
    asyncio.run(stress(url_str, 100, 1))    # MODERATE STRESS
    asyncio.run(stress(url_str, 1000, 5))   # LONG STRESS


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
        APIRequest(                     # NO PARAMETERS
            url,
            {},
        )
    ]

    reses = [r.perform_request() for r in reqs]

    assert all([not res.timeout for res in reses]), "Some of the requests timed out (try running the tests again)"
    assert all([res.status == 400 for res in reses]), "Some of the requests did not finish with Bad Request"
