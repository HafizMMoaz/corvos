"""Check DB state: users, model connections, global configs."""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

import sqlalchemy as sa

DB = "postgresql+asyncpg://corvos:corvos@localhost:5432/corvos"


async def check():
    eng = sa.create_async_engine(DB)
    async with eng.connect() as c:
        users = (await c.execute(sa.text("SELECT id, email FROM users ORDER BY id"))).fetchall()
        print("USERS:", [(u[0], u[1]) for u in users])
        try:
            conns = (
                await c.execute(
                    sa.text("SELECT id, user_id, provider, is_active FROM model_connections ORDER BY id")
                )
            ).fetchall()
            print("MODEL_CONNECTIONS:", [(x[0], x[1], x[2], x[3]) for x in conns])
        except Exception as e:
            print("model_connections err:", str(e)[:200])
        try:
            cfgs = (
                await c.execute(sa.text("SELECT id, name, is_active FROM global_configs ORDER BY id"))
            ).fetchall()
            print("GLOBAL_CONFIGS:", [(x[0], x[1], x[2]) for x in cfgs])
        except Exception as e:
            print("global_configs err:", str(e)[:200])
    await eng.dispose()


asyncio.run(check())
