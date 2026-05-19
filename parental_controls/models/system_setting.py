from sqlmodel import Field, SQLModel


class SystemSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
