import errno
import time
from urllib import request
from urllib.error import URLError

t0 = time.time()
found = False
url = 'http://localhost:5000'

while (time.time() - t0) < 60:
    try:
        request.urlopen(url)
        found = True
        break
    except URLError as e:
        if e.reason.errno == errno.ECONNREFUSED:
            time.sleep(1)
            continue
        raise


if not found:
    raise ValueError(f'Could not connect to {url}')
