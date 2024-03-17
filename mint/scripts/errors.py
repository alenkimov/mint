from ..database import MintAccount


class MintScriptLogicException(Exception):
    def __init__(self, account: MintAccount, exception_message: str):
        self.account = account

        super().__init__(f"[{self.account}] {exception_message}")


class TooLessTwitterFollowers(MintScriptLogicException):
    pass
