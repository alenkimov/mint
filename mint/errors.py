from .account import Account
# from .api.errors import HTTPException


class MintScriptLogicException(Exception):
    def __init__(self, account: Account, exception_message: str):
        self.account = account

        super().__init__(f"[{self.account}] {exception_message}")


class TooLessTwitterFollowers(MintScriptLogicException):
    pass


# class Error(MintScriptLogicException):
    # def __init__(self, account: Account, exception_message: str, *, http_exception: HTTPException):
    #     self.http_exception = http_exception
    #     super().__init__(account, exception_message)
