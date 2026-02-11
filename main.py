#!/usr/bin/env python3
from dotenv import load_dotenv
load_dotenv()  # Loads variables from .env file
from cli.commands import cli

if __name__ == '__main__':
    cli()