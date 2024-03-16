from tortoise import fields

# from twitter.utils import hidden_value


class DatabaseIDMixin:
    database_id = fields.IntField(pk=True)

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id})"


# class IDMixin:
#     id = fields.IntField(null=True, unique=True, index=True)


# class AuthTokenMixin(DatabaseIDMixin):
#     auth_token = fields.TextField(unique=True, null=True)
#
#     @property
#     def hidden_auth_token(self) -> str | None:
#         return hidden_value(self.auth_token) if self.auth_token else None
#
#     def __repr__(self):
#         return f"{self.__class__.__name__}(database_id={self.database_id}, auth_token={self.hidden_auth_token})"


# class AccountMixin(DatabaseIDMixin):
#     ...


# class UserMixin(DatabaseIDMixin):
#     ...
