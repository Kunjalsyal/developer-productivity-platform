from app.services.embeddings import HashEmbedder, code_tokens


def cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_tokens_split_snake_and_camel():
    assert code_tokens("enforceRateLimit user_id") == ["enforce", "rate", "limit", "user", "id"]


def test_hash_embedder_normalised_and_ranks_related_text_higher():
    e = HashEmbedder(384)
    q, rel, other = e.embed(["rate limit", "def enforce_rate_limit(request): rate limit token bucket",
                             "def render_invoice_pdf(order): draw table"])
    assert abs(cos(q, q) - 1) < 1e-6
    assert cos(q, rel) > cos(q, other)
