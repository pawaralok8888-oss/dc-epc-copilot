from src.ai.extract import read_pdf_chunks, extract_requirements, save_requirements

PDF = "data/spec.pdf"
ATTEMPTS = 3

all_reqs = []
for i, chunk in enumerate(read_pdf_chunks(PDF), start=1):
    for attempt in range(1, ATTEMPTS + 1):
        try:
            reqs = extract_requirements(chunk)
            all_reqs.extend(reqs)
            print(f"chunk {i}: {len(reqs)} requirements (attempt {attempt})")
            break
        except Exception as e:
            print(f"chunk {i}: attempt {attempt} FAILED ({e})")
    else:
        print(f"chunk {i}: gave up after {ATTEMPTS} attempts")

seen = {}
for r in all_reqs:
    seen.setdefault(r.clause_id, r)
all_reqs = list(seen.values())

save_requirements(all_reqs)
print(f"saved {len(all_reqs)} unique requirements")
