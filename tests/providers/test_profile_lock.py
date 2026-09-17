from pathlib import Path

import pytest

from lifeos.profile_lock import ProfileInUse, ProfileLease


def test_browser_profile_is_owned_by_one_process_at_a_time(tmp_path: Path):
    first = ProfileLease(tmp_path)
    second = ProfileLease(tmp_path)
    first.acquire()
    try:
        with pytest.raises(ProfileInUse):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()
