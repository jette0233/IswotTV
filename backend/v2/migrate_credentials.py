import asyncio

from sqlalchemy import select

from v2.db import SessionLocal, User
from v2.security import encrypt_credential


async def migrate():
    changed = 0
    async with SessionLocal() as session:
        users = (await session.scalars(select(User).where(User.cookie_manual.is_not(None), User.cookie_manual != ""))).all()
        for user in users:
            if not user.cookie_manual.startswith("enc:v1:"):
                user.cookie_manual = encrypt_credential(user.cookie_manual)
                changed += 1
        await session.commit()
    print(f"encrypted {changed} stored credentials")


if __name__ == "__main__":
    asyncio.run(migrate())
