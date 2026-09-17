"""Keep automated tests independent of the operator's populated .env credentials."""

import os

# Apply before backend conftest imports create the module-level application.
# Explicit Settings(...) arguments in individual tests still take precedence.
os.environ.update(
    {
        "LIFEOS_MODE": "demo",
        "LIFEOS_ENVIRONMENT": "test",
        "LIFEOS_DATABASE_URL": "sqlite:///:memory:",
        "LIFEOS_AUTH_PASSWORD": "",
        "LIFEOS_ENCRYPTION_KEY": "",
        "LIFEOS_OPENAI_API_KEY": "",
        "LIFEOS_GOOGLE_CLIENT_ID": "",
        "LIFEOS_GOOGLE_CLIENT_SECRET": "",
        "LIFEOS_DISCORD_BOT_TOKEN": "",
        "LIFEOS_DISCORD_CHANNEL_ID": "",
        "LIFEOS_WHATSAPP_ENABLED": "false",
        "LIFEOS_WHATSAPP_CONTACT": "",
    }
)
