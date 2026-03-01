#!/usr/bin/env python3
"""Entry point for ensemble_agent — works as a standalone script."""
import asyncio
from ensemble_agent.config import parse_args
from ensemble_agent.agent import run_agent

asyncio.run(run_agent(parse_args()))
