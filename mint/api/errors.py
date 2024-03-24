from curl_cffi import requests


class MintException(Exception):
    pass


class HTTPException(MintException):
    def __init__(self, response: requests.Response, data: dict):
        self.response = response
        self.code = None
        self.message = None

        exception_message = f"(response status: {response.status_code})"

        if isinstance(data, str):
            self.message = data or "No error message"
            exception_message += f" {self.message}"
        else:
            self.code = data.get("code")
            self.message = data.get("msg", "No error message")
            exception_message += f"\n\t(code: {self.code}) {self.message}"

        super().__init__(exception_message)
