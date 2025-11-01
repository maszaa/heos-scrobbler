import pytest
from faker import Faker
from pylast import LastFMNetwork


@pytest.fixture
def last_fm_network(faker: Faker) -> LastFMNetwork:
    return LastFMNetwork(
        api_key=faker.random_letter(), api_secret=faker.random_letter(), session_key=faker.random_letter()
    )
