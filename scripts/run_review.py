#!/usr/bin/env python3
"""Test script to run a PR review locally."""
import asyncio
from dotenv import load_dotenv

load_dotenv()

from src.services.reviewer.service import review_pull_request

async def main():
    result = await review_pull_request(
        owner="jim302",
        repo="test-pr-reviewer", 
        pr_number=1
    )
    print(f"Review result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
