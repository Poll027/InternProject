import hashlib

def generate_item_hash(source_name, title, url, published_date):
    raw = f"{source_name} | {title} | {url} | {published_date}"
    return hashlib.sha256(raw.encode()).hexdigest()

if __name__ == "__main__":
    h1 = generate_item_hash("CBN", "Circular on FX", "https://cbn.gov.ng/x", "2026-07-01")
    h2 = generate_item_hash("CBN", "Circular on FX", "https://cbn.gov.ng/x", "2026-07-01")
    print(h1)
    print(h2)
    print("Deterministic:", h1 == h2)

    