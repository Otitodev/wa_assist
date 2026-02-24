#!/usr/bin/env python3
"""
Bulk domain availability checker via Porkbun API v3.

Setup:
    pip install aiohttp

Usage:
    python check_domains.py

Get API keys at: https://porkbun.com/account/api
"""

import asyncio
import json
import sys
import aiohttp

# ── Configure these ──────────────────────────────────────────────────────────

PORKBUN_API_KEY    = "pk1_your_api_key_here"
PORKBUN_SECRET_KEY = "sk1_your_secret_key_here"

# Name roots to check
NAME_ROOTS = [
    "replai",
    "relaiq",
    "attache",
    "liaise",
    "deskly",
    "deskra",
    "inboxly",
    "greeva",
    "auxly",
    "proxa",
    "nexly",
    "quilo",
    "repty",
    "assistr",
    "caden",
    "whaply",
    "wapli",
]

# TLDs to check per root
TLDS = [".com", ".io", ".co", ".ai", ".app"]

# ── Constants ────────────────────────────────────────────────────────────────

API_BASE    = "https://api.porkbun.com/api/json/v3/domain/checkDomain"
CONCURRENCY = 8   # max parallel requests (be polite to the API)

# ANSI colours
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GREY   = "\033[90m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Core ─────────────────────────────────────────────────────────────────────

async def check_domain(
    session: aiohttp.ClientSession,
    domain: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    async with semaphore:
        url     = f"{API_BASE}/{domain}"
        payload = {"apikey": PORKBUN_API_KEY, "secretapikey": PORKBUN_SECRET_KEY}
        try:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                data = await resp.json(content_type=None)

                if data.get("status") != "SUCCESS":
                    return {
                        "domain":    domain,
                        "available": False,
                        "price":     None,
                        "regular":   None,
                        "premium":   False,
                        "error":     data.get("message", "Unknown error"),
                    }

                r = data.get("response", {})
                return {
                    "domain":    domain,
                    "available": r.get("avail", "no") == "yes",
                    "price":     r.get("price"),
                    "regular":   r.get("regularPrice"),
                    "premium":   r.get("premium", "no") == "yes",
                    "error":     None,
                }

        except asyncio.TimeoutError:
            return {"domain": domain, "available": None, "price": None,
                    "regular": None, "premium": False, "error": "Timeout"}
        except Exception as exc:
            return {"domain": domain, "available": None, "price": None,
                    "regular": None, "premium": False, "error": str(exc)}


async def run():
    domains = [f"{root}{tld}" for root in NAME_ROOTS for tld in TLDS]

    print(f"\n{BOLD}Checking {len(domains)} domains across "
          f"{len(NAME_ROOTS)} names × {len(TLDS)} TLDs ...{RESET}\n")

    semaphore = asyncio.Semaphore(CONCURRENCY)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks   = [check_domain(session, d, semaphore) for d in domains]
        results = await asyncio.gather(*tasks)

    available = [r for r in results if r["available"] is True]
    taken     = [r for r in results if r["available"] is False and not r["error"]]
    errors    = [r for r in results if r["error"]]

    # ── Print available ───────────────────────────────────────────────────────
    if available:
        print(f"{BOLD}{'── AVAILABLE ':─<55}{RESET}")
        # Sort: non-premium first, then by price
        available.sort(key=lambda r: (r["premium"], float(r["price"] or 99)))
        for r in available:
            promo   = f"{GREEN}${r['price']}/yr{RESET}"
            regular = f"{GREY}(renews ${r['regular']}){RESET}" if r["regular"] else ""
            premium = f" {YELLOW}[PREMIUM]{RESET}" if r["premium"] else ""
            print(f"  {GREEN}✓{RESET}  {r['domain']:<28} {promo} {regular}{premium}")
    else:
        print(f"  {RED}No domains available.{RESET}")

    # ── Print taken ───────────────────────────────────────────────────────────
    if taken:
        print(f"\n{BOLD}{'── TAKEN ':─<55}{RESET}")
        for r in taken:
            print(f"  {RED}✗{RESET}  {GREY}{r['domain']}{RESET}")

    # ── Print errors ──────────────────────────────────────────────────────────
    if errors:
        print(f"\n{BOLD}{'── ERRORS ':─<55}{RESET}")
        for r in errors:
            print(f"  ?  {r['domain']:<28} {YELLOW}{r['error']}{RESET}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}Summary:{RESET} "
          f"{GREEN}{len(available)} available{RESET}  "
          f"{RED}{len(taken)} taken{RESET}  "
          f"{YELLOW}{len(errors)} errors{RESET}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "your_api_key_here" in PORKBUN_API_KEY:
        print(f"\n{RED}Error:{RESET} Set your Porkbun API keys at the top of this file.")
        print("Get them at: https://porkbun.com/account/api\n")
        sys.exit(1)

    asyncio.run(run())
