from .database import MintAccount, TwitterAccount, DiscordAccount


class ScriptError(Exception):
    pass


class MintScriptError(ScriptError):
    def __init__(self, account: MintAccount, exception_message: str):
        self.account = account
        super().__init__(f"{account} {exception_message}")


class TwitterScriptError(ScriptError):
    def __init__(self, account: TwitterAccount, exception_message: str):
        self.account = account
        super().__init__(f"{account} {exception_message}")


class DiscordScriptError(ScriptError):
    def __init__(self, account: DiscordAccount, exception_message: str):
        self.account = account
        super().__init__(f"{account} {exception_message}")
