import requests
import urllib3
from itertools import cycle

# Unenables SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROXY_LIST = [
    {
        "http": "http://brd-customer-hl_961a5843-zone-gmgnscrapper:a4ypx1ve1qcr@brd.superproxy.io:33335",
        "https": "http://brd-customer-hl_961a5843-zone-gmgnscrapper:a4ypx1ve1qcr@brd.superproxy.io:33335"
    },
]

proxy_cycle = cycle(PROXY_LIST)

def get_data_with_proxy(url: str, headers: dict = None, json_payload: dict = None, timeout: int = 60) -> requests.Response:
    """
    Performs an HTTP request with a Bright Data proxy and SSL disabled.
    
    Args:
        url (str): Target URL of the request.
        headers (dict, optional): HTTP headers for the request.
        json_payload (dict, optional): JSON payload for POST requests.
        timeout (int): Request timeout in seconds.
    
    Returns:
        requests.Response: API response.
    
    Raises:
        RuntimeError: In case of request failure.
    """
    try:
        current_proxy = next(proxy_cycle)
        
        session = requests.Session()
        session.proxies.update(current_proxy)

        # Effectuer une requête GET ou POST
        if json_payload is not None:
            # POST with JSON payload
            response = session.post(url, headers=headers, json=json_payload, verify=False, timeout=timeout)
        else:
            # GET classique
            response = session.get(url, headers=headers, verify=False, timeout=timeout)
        
        response.raise_for_status()  # Vérifies HTTP errors
        return response
    except requests.Timeout:
        raise RuntimeError(f"Reaching timeout while requesting {url}.")
    except requests.RequestException as e:
        raise RuntimeError(f"HTTP error while requesting {url}: {str(e)}")
