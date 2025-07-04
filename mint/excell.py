from common.excell import Excel, Column

# fmt: off
COLUMNS = [
    Column("Group",       "Group name",                    "group", max_length=16),
    Column("Proxy",       "Proxy: any format",             "proxy"),
    Column("Invite code", "Referrer invite code",          "invite_code", group_name="mint"),
    Column("Private key", "Private key",                   "private_key", group_name="wallet", required=True),
    Column("Token",       "Twitter auth_token",            "auth_token",  group_name="twitter"),
    Column("Email",       "Twitter email",                 "email",       group_name="twitter"),
    Column("Username",    "Twitter username",              "username",    group_name="twitter"),
    Column("Password",    "Twitter password",              "password",    group_name="twitter"),
    Column("TOTP secret", "Twitter TOTP secret key (2FA)", "totp_secret", group_name="twitter"),
    Column("Token",       "Discord token",                 "auth_token",  group_name="discord"),
]
# fmt: on

excell = Excel(COLUMNS)

