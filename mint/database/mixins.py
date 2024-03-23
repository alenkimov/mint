from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class DatabaseIDMixin:
    database_id: Mapped[int] = mapped_column(primary_key=True)

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id})"


class IDMixin:
    id: Mapped[int] = mapped_column(primary_key=True)

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id})"


# TODO Переделать AuthTokenMixin на Annotated
class AuthTokenMixin:
    auth_token: Mapped[str | None] = mapped_column(unique=True)


# TODO Переделать EmailMixin на Annotated
class EmailMixin:
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
