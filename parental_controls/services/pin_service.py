import bcrypt
from sqlmodel import Session

from parental_controls.models.system_setting import SystemSetting

_ADMIN_PIN_KEY = "admin_pin_hash"


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode(), pin_hash.encode())


def get_admin_pin_hash(session: Session) -> str:
    from parental_controls.config import settings
    row = session.get(SystemSetting, _ADMIN_PIN_KEY)
    return row.value if row else settings.admin_pin_hash


def set_admin_pin_hash(session: Session, new_hash: str) -> None:
    row = session.get(SystemSetting, _ADMIN_PIN_KEY)
    if row:
        row.value = new_hash
    else:
        row = SystemSetting(key=_ADMIN_PIN_KEY, value=new_hash)
    session.add(row)
    session.commit()
