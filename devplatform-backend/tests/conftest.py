import os

# Must run before `app` is imported anywhere.
os.environ["EMBEDDING_BACKEND"] = "hash"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["AUTO_CREATE_SCHEMA"] = "false"
if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
