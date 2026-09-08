"""Тестовый скрипт: получение stories пользователя VK ID 311642773 — v4.

Новые токены от пользователя (2026-09-08).

Запуск: python scripts/test_vk_stories.py
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SECRETS_DIR = Path("D:/AI/secrets")

def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""

# Новые токены от пользователя
TOKEN_NEW_1 = "vk1.a.9x5ou19VEzmlNQbcrT9U_v_gCl0BMjrFFrwi02hyXxo6ixHnliKSfPcVHOND9MTcUv0soC82sFmdR8En2Vj_MtpQfJ9AR1jsJsHNUm12OEaFhS5F_SuvIXeUg6i9Zg91i9jCDrK5whIxIMsqZMDpAx6voYuEb4CaGXjsJFxcGuLVZEQflijmL9ldcxUQ_5bKIkaWFAP7rU5TwRZopLC8rg"
TOKEN_NEW_2 = "vk1.a.PhRcRE11UMv_YHl07YSzDKgXJgVK76rhtVBtaHmuOLro49f_m1cDovp8DF1oO_fAl1awMzVolTe7mtJQVUfqXeA1n98MTY-FNwYGsvHPae9W-OxpDUNgofB7CIXvFiCJ2FJ_jqssSdMooLHDF1_1eLk-T5QGmLhGCISGJzk9kFB3W3liy2D_AKxCh5fXwmp_"

TOKENS = [TOKEN_NEW_1, TOKEN_NEW_2]

TARGET_USER_ID = 311642773

print(f"Токенов для теста: {len(TOKENS)}")


def fmt_resp(title: str, data: dict) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    if not isinstance(data, dict):
        print(f"  [ERROR] {type(data).__name__}: {str(data)[:200]}")
        return
    if "error" in data:
        err = data["error"]
        if isinstance(err, dict):
            print(f"  [ERROR] VK API: code={err.get('error_code')}, msg={err.get('error_msg')}")
        elif isinstance(err, str):
            print(f"  [ERROR] {err[:200]}")
        else:
            print(f"  [ERROR] {err}")
        return
    resp = data.get("response")
    if resp is None:
        print(f"  [DEBUG] keys: {list(data.keys())}")
        return
    if isinstance(resp, list) and resp and "first_name" in resp[0]:
        u = resp[0]
        print(f"  [OK] {u.get('first_name')} {u.get('last_name')} (id={u.get('id')})")
        return
    if isinstance(resp, dict):
        items = resp.get("items", [])
        profiles = resp.get("profiles", [])
        groups = resp.get("groups", [])
        print(f"  [OK] Stories: {len(items)} шт., profiles: {len(profiles)}, groups: {len(groups)}")
        if not items:
            print(f"  [INFO] Нет активных stories.")
            return
        for i, s in enumerate(items, 1):
            sid = s.get("id", "?")
            stype = s.get("type", "?")
            ts = datetime.fromtimestamp(s.get("date", 0)).strftime("%Y-%m-%d %H:%M:%S") if s.get("date") else "?"
            expired = s.get("is_expired", False)
            can_see = s.get("can_see", 1)
            print(f"  [{i}] id={sid}, type={stype}, date={ts}, expired={expired}, can_see={can_see}")
            if stype == "photo" and "photo" in s:
                print(f"       photo: {s['photo'].get('url','?')[:100]}...")
            elif stype == "video" and "video" in s:
                v = s["video"]
                print(f"       video: duration={v.get('duration','?')}s, url={v.get('url','?')[:100]}...")
        print(f"  [INFO] Всего: {len(items)} stories, expired: {sum(1 for s in items if s.get('is_expired'))}")
        return


# ---------------------------------------------------------------------------
# HTTP прямой запрос
# ---------------------------------------------------------------------------
async def try_http(token: str, label: str) -> dict:
    import httpx
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get("https://api.vk.com/method/stories.get", params={
            "owner_id": TARGET_USER_ID, "extended": 1,
            "access_token": token, "v": "5.199",
        })
        return resp.json()


# ---------------------------------------------------------------------------
# vkbottle
# ---------------------------------------------------------------------------
async def try_vkbottle(token: str, label: str) -> dict:
    from vkbottle import API
    api = API(token=token)
    try:
        response = await api.stories.get(owner_id=TARGET_USER_ID, extended=1)
        return response.dict() if hasattr(response, "dict") else response
    except Exception as e:
        return {"error": str(e), "error_type": type(e).__name__}


# ---------------------------------------------------------------------------
# Проверка токена (users.get)
# ---------------------------------------------------------------------------
async def check_token(token: str, label: str) -> dict:
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get("https://api.vk.com/method/users.get", params={
            "user_ids": TARGET_USER_ID, "access_token": token, "v": "5.199",
        })
        return resp.json()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
async def main() -> None:
    print("=" * 60)
    print("  ТЕСТ v4: stories пользователя VK ID 311642773")
    print(f"  Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = {}

    for i, token in enumerate(TOKENS, 1):
        print(f"\n{'─'*60}")
        print(f"  ТОКЕН {i}: {token[:30]}...{token[-8:]}")
        print(f"{'─'*60}")

        # Проверка валидности токена
        check = await check_token(token, f"token_{i}")
        fmt_resp(f"check users.get token_{i}", check)
        results[f"check_token_{i}"] = check

        if "error" in check:
            print(f"  [SKIP] Токен {i} невалиден, пропускаем stories.get")
            continue

        # HTTP stories.get
        resp_http = await try_http(token, f"token_{i}")
        fmt_resp(f"HTTP stories.get token_{i}", resp_http)
        results[f"http_token_{i}"] = resp_http

        # vkbottle stories.get
        resp_vk = await try_vkbottle(token, f"token_{i}")
        fmt_resp(f"vkbottle stories.get token_{i}", resp_vk)
        results[f"vkbottle_token_{i}"] = resp_vk

    # Сохраняем
    output_file = PROJECT_ROOT / "scripts" / "vk_stories_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "target_user_id": TARGET_USER_ID, "results": results},
                  f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[OK] Результаты: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())