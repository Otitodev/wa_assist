"""
Shared pytest fixtures and configuration.
"""
import os
import sys

# Ensure the project root is on the Python path so `app.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set dummy env vars so config.py doesn't error on import
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("CF_R2_ACCOUNT_ID", "test-account")
os.environ.setdefault("CF_R2_ACCESS_KEY_ID", "test-key-id")
os.environ.setdefault("CF_R2_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("CF_R2_PUBLIC_URL", "https://pub-test.r2.dev")
