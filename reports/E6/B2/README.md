# E6 B2 Candidate Acquisition

- **B2 responsibility:** Acquire a fresh error-driven Dockerfile candidate and preserve its prompt, response, and provenance.
- **B1 input:** Branch `e6-b1`, commit `616049de002dc869fb113a3ce8358d7983f23f1d`.
- **Files:** `README.md` records the acquisition and handoff; `prompt.txt` is the exact generation prompt; `model-response.txt` preserves the full response; `candidate.Dockerfile` is extracted unchanged from that response; `provenance.json` records source, hashes, comparison, and status.
- **Prompt strategy:** Error-driven repair of the reported missing `make` build tool, with the required base image, package installation, build, and runtime constraints.
- **Candidate SHA-256:** `510dc459a9a3830aabdf35b32c15b0c22a3c3299982950e40378d4a3227b9788`.
- **E5 comparison:** The candidate is not byte-identical to any of the three E5 candidates. E5 SHA-256 values: candidate-1 `ede21b0fab394071641526e2fccefc41565efb00de6fb54d9d5b906aebeb535d`; candidate-2 `027d8aabcd8d192cac5353831afe51c7d600fabf28528936ea9c9f715d3fb95c`; candidate-3 `a78a103b453f83a7405172a850f73cd88a4da9addb654a918118f37554a30a24`.
- **Status:** `RECEIVED_NOT_BUILT`.
- **Not performed:** Docker build, image run, and B3 verification.
- **Handoff:** E6 B3 should use the B1 auto-build flow.
